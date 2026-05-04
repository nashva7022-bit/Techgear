from django.db import models
from django.conf import settings
from products.models import ProductVariant, Product
from django.core.validators import MinValueValidator, MaxValueValidator


from cloudinary.models import CloudinaryField
# ──────────────────────────────────────────
# CART
# One cart per user.
# Created automatically when user first
# adds a product to cart.
# ──────────────────────────────────────────

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user.email}"

    @property
    def total_items(self):
        """Total quantity of all items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        """Sum of all item subtotals. Only counts available items."""
        return sum(
            item.subtotal
            for item in self.items.all()
            if item.is_available
        )

    @property
    def has_out_of_stock(self):
        """True if ANY item in cart is out of stock."""
        return any(not item.is_in_stock for item in self.items.all())

    @property
    def has_unavailable(self):
        """True if ANY item's product/category was deactivated after adding to cart."""
        return any(not item.is_available for item in self.items.all())


# ──────────────────────────────────────────
# CART ITEM
# ──────────────────────────────────────────

class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant  = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)

    # Customization fields — only for Phone Cases and Laptop Skins
    custom_text  = models.CharField(max_length=100, blank=True, default='')
    custom_image = CloudinaryField('custom_image', blank=True, null=True)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.variant_display} × {self.quantity}"

    @property
    def variant_display(self):
        parts   = []
        variant = self.variant
        product = variant.product
        if variant.device_model:
            parts.append(variant.device_model.name)
        if variant.case_type and product.is_customizable:
            parts.append(variant.get_case_type_display())
        parts.append(variant.get_color_display())
        return ' — '.join(parts)

    @property
    def subtotal(self):
        return self.variant.discounted_price * self.quantity

    @property
    def is_available(self):
        return (
            self.variant.is_active and
            self.variant.product.is_active and
            self.variant.product.category.is_active
        )

    @property
    def is_in_stock(self):
        return self.variant.stock >= self.quantity

    @property
    def max_quantity(self):
        return min(5, self.variant.stock)

    @property
    def is_customizable(self):
        return self.variant.product.is_customizable

    @property
    def primary_image(self):
        return self.variant.images.filter(is_primary=True).first() or self.variant.images.first()

    @property
    def product_name(self):
        return self.variant.product.name

    @property
    def category_name(self):
        return self.variant.product.category.name

    @property
    def brand(self):
        return self.variant.product.get_brand_display()

    @property
    def price(self):
        return self.variant.price

    @property
    def stock(self):
        return self.variant.stock

    @property
    def colour(self):
        return self.variant.get_color_display()

    @property
    def colour_code(self):
        return self.variant.color_code

    @property
    def device_model(self):
        return self.variant.device_model.name if self.variant.device_model else ''

    @property
    def case_type(self):
        if self.is_customizable and self.variant.case_type:
            return self.variant.get_case_type_display()
        return ''


# ──────────────────────────────────────────
# WISHLIST
# One wishlist per user.
# Stores products (not variants) —
# user picks variant when they move to cart.
# ──────────────────────────────────────────

class Wishlist(models.Model):
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist of {self.user.email}"

    @property
    def total_items(self):
        return self.items.count()


# ──────────────────────────────────────────
# WISHLIST ITEM
# Stores a product in the wishlist.
# unique_together prevents duplicates.
# ──────────────────────────────────────────

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product  = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['wishlist', 'product']
        ordering        = ['-added_at']

    def __str__(self):
        return f"{self.product.name} in {self.wishlist.user.email}'s wishlist"

    @property
    def is_available(self):
        """Product and category must both be active."""
        return (
            self.product.is_active and
            self.product.category.is_active
        )

    @property
    def primary_image(self):
        first_variant = self.product.variants.filter(is_active=True).first()
        if first_variant:
            return first_variant.images.filter(is_primary=True).first() or first_variant.images.first()
        return None

    @property
    def min_price(self):
        return self.product.min_price
    



class Review(models.Model):
    product    = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating     = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'user']  # one review per user per product
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — {self.product.name} ({self.rating}★)"