from django.db import models
from cloudinary.models import CloudinaryField
from django.utils.text import slugify
import random, string
from django.core.validators import MinValueValidator, MaxValueValidator




# BRAND CHOICES

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



# CASE TYPE CHOICES

CASE_TYPE_CHOICES = [
    ('slim',     'Slim Fit'),
    ('rugged',   'Rugged Armor'),
    ('wallet',   'Wallet Folio'),
    ('clear',    'Crystal Clear'),
    ('leather',  'Leather Finish'),
    ('magsafe',  'MagSafe Compatible'),
    ('bumper',   'Bumper Case'),
    ('military', 'Military Grade'),
    ('thin',     'Ultra Thin'),
    ('matte',    'Matte Finish'),
    ('other',    'Other'),
    ('dell', 'Dell'),
    ('hp', 'HP'),
]



# DEVICE MODEL

class DeviceModel(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('phone',  'Phone'),
        ('laptop', 'Laptop'),
    ]
    brand     = models.CharField(max_length=50, choices=BRAND_CHOICES)
    name      = models.CharField(max_length=100)   # e.g. "iPhone 15 Pro"
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES, default='phone')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering        = ['brand', 'name']
        unique_together = ['brand', 'name']
        verbose_name        = 'Device Model'
        verbose_name_plural = 'Device Models'

    def __str__(self):
        return f"{self.get_brand_display()} — {self.name}"



# CATEGORY


class Category(models.Model):
    DEVICE_TYPE_CHOICES = [
    ('phone', 'Phone'),
    ('laptop', 'Laptop'),
]

    device_type = models.CharField(
        max_length=10,
        choices=DEVICE_TYPE_CHOICES,
        default='phone'
    )
    name            = models.CharField(max_length=100)
    slug            = models.SlugField(max_length=100, unique=True, blank=True)
    description     = models.TextField(blank=True)
    image           = CloudinaryField('image', blank=True, null=True)

    # Phone cases and laptop skins are customizable; grips and screen protectors are not.
    is_customizable = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)

    # Controls whether the Case Type field is shown in product variants.
    # True for: Phone Cases, Laptop Skins.
    # False for: Grips, Screen Protectors, etc.
    has_case_type   = models.BooleanField(default=False)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering            = ['-created_at']
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


class CategorySpecTemplate(models.Model):
    """Defines which spec names belong to a category."""
    category    = models.ForeignKey(Category, on_delete=models.CASCADE,
                                    related_name='spec_templates')
    name        = models.CharField(max_length=100)   # e.g. "Material"
    placeholder = models.CharField(max_length=100, blank=True)  # hint text
    order       = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.category.name} → {self.name}"


# PRODUCT


class Product(models.Model):
    category    = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    name        = models.CharField(max_length=150)
    slug        = models.SlugField(max_length=150, unique=True, blank=True)
    brand       = models.CharField(max_length=50, choices=BRAND_CHOICES, default='other')
    description = models.TextField(blank=True)

    is_active               = models.BooleanField(default=True)
    
    deactivated_by_category = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)


    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug      = base_slug
            counter   = 1
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
        prices = list(
        self.variants.filter(is_active=True).values_list('price', flat=True)
    )
        return min(prices) if prices else None

    @property
    def min_discounted_price(self):
        variants = self.variants.filter(is_active=True)
        prices = [v.discounted_price for v in variants]
        return min(prices) if prices else None

    @property
    def has_discount(self):
        return self.variants.filter(
            is_active=True,
            discount_percentage__gt=0
        ).exists()

    

    @property
    def active_variant(self):
        return self.variants.filter(is_active=True).first()

# PRODUCT SPECIFICATION


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

# PRODUCT VARIANT


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
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )

    # FK to DeviceModel — always required for all categories.
   
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='variants',
    )

    # Choices — only meaningful when category.has_case_type is True.
    # Blank for grips, screen protectors, etc.
    case_type = models.CharField(
        max_length=50,
        choices=CASE_TYPE_CHOICES,
        blank=True,
        default='',
    )

    color      = models.CharField(max_length=50, choices=COLOR_CHOICES, default='black')
    color_code = models.CharField(max_length=7, default='#000000')   # hex
    sku        = models.CharField(max_length=50, unique=True, blank=True, null=True)
    price      = models.DecimalField(max_digits=10, decimal_places=2)
    stock      = models.PositiveIntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.sku:
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
                    self.sku = None
            raise ValueError("Could not generate a unique SKU after 10 attempts.")
        super().save(*args, **kwargs)

    def __str__(self):
        device = self.device_model.name if self.device_model else 'No Device'
        return f"{self.product.name} — {device} — {self.color}"

    @property
    def primary_image(self):
        return self.images.first()
    

    discount_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0),MaxValueValidator(90)] , # max 90% discount
         help_text='Discount percentage 0-90%'
    )

    @property
    def discounted_price(self):
        if self.discount_percentage:
            discount = (self.price * self.discount_percentage) / 100
            return round(self.price - discount, 2)
        return self.price

    @property
    def has_discount(self):
        return self.discount_percentage > 0


# VARIANT IMAGE


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