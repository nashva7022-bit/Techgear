from django.db import models
from cloudinary.models import CloudinaryField
from django.utils.text import slugify
import random, string


# ──────────────────────────────────────────
# CATEGORY
# ──────────────────────────────────────────

class Category(models.Model):
    name            = models.CharField(max_length=100)
    slug            = models.SlugField(max_length=100, unique=True, blank=True)
    description     = models.TextField(blank=True)
    image           = CloudinaryField('image', blank=True, null=True)  # optional thumbnail
    # Customization lives HERE — it's a category trait, not a product trait.
    # Phone cases and laptop skins are customizable; grips and screen protectors are not.
    is_customizable = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()


# ──────────────────────────────────────────
# PRODUCT
# ──────────────────────────────────────────

BRAND_CHOICES = [
    ('apple',    'Apple'),
    ('samsung',  'Samsung'),
    ('oneplus',  'OnePlus'),
    ('google',   'Google'),
    ('xiaomi',   'Xiaomi'),
    ('realme',   'Realme'),
    ('oppo',     'OPPO'),
    ('vivo',     'Vivo'),
    ('nothing',  'Nothing'),
    ('motorola', 'Motorola'),
    ('other',    'Other'),
]


class Product(models.Model):
    category    = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    name        = models.CharField(max_length=150)
    slug        = models.SlugField(max_length=150, unique=True, blank=True)
    brand       = models.CharField(max_length=50, choices=BRAND_CHOICES, default='other')
    description = models.TextField(blank=True)
    # NOTE: is_customizable is REMOVED from Product.
    # Use product.category.is_customizable to check whether a product supports customization.
    is_active               = models.BooleanField(default=True)
    # Set to True when deactivated by a category cascade — lets us restore only
    # these products when the category is re-activated, leaving manually-deactivated
    # products untouched.
    deactivated_by_category = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def is_customizable(self):
        """Delegate to category. Safe even if category is null."""
        return bool(self.category and self.category.is_customizable)

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants.filter(is_active=True))

    @property
    def primary_image(self):
        first_variant = self.variants.filter(is_active=True).first()
        if first_variant:
            return first_variant.images.first()
        return None

    @property
    def min_price(self):
        prices = list(self.variants.filter(is_active=True).values_list('price', flat=True))
        return min(prices) if prices else None


# ──────────────────────────────────────────
# PRODUCT SPECIFICATION
# ──────────────────────────────────────────

class ProductSpecification(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='specifications'
    )
    name    = models.CharField(max_length=100)   # e.g. "Material"
    value   = models.CharField(max_length=255)   # e.g. "Polycarbonate"
    order   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} — {self.name}: {self.value}"


# ──────────────────────────────────────────
# PRODUCT VARIANT
# ──────────────────────────────────────────

COLOR_CHOICES = [
    ('black',       'Black'),
    ('white',       'White'),
    ('red',         'Red'),
    ('blue',        'Blue'),
    ('green',       'Green'),
    ('yellow',      'Yellow'),
    ('orange',      'Orange'),
    ('purple',      'Purple'),
    ('pink',        'Pink'),
    ('grey',        'Grey'),
    ('navy',        'Navy'),
    ('gold',        'Gold'),
    ('silver',      'Silver'),
    ('transparent', 'Transparent'),
    ('other',       'Other'),
]


class ProductVariant(models.Model):
    product      = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )
    device_model = models.CharField(max_length=100)           # e.g. "iPhone 15 Pro"
    case_type    = models.CharField(max_length=50, blank=True) # e.g. "Slim", "Rugged"
    color        = models.CharField(max_length=50, choices=COLOR_CHOICES, default='black')
    color_code   = models.CharField(max_length=7, default='#000000')  # hex
    sku          = models.CharField(max_length=50, unique=True, blank=True, null=True)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    stock        = models.PositiveIntegerField(default=0)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.sku:
            # Retry loop guards against the rare random collision.
            from django.db import IntegrityError
            for _ in range(10):
                base   = self.product.name.upper().replace(' ', '-')[:8]
                color  = self.color.upper()[:3]
                suffix = ''.join(random.choices(string.digits, k=4))
                self.sku = f"{base}-{color}-{suffix}"
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    self.sku = None  # try again
            raise ValueError("Could not generate a unique SKU after 10 attempts.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — {self.device_model} — {self.color}"

    @property
    def primary_image(self):
        return self.images.first()


# ──────────────────────────────────────────
# VARIANT IMAGE
# ──────────────────────────────────────────

class VariantImage(models.Model):
    variant    = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='images'
    )
    image      = CloudinaryField('image')
    is_primary = models.BooleanField(default=False)
    order      = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image for variant {self.variant.id}"