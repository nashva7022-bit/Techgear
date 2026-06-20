from django.db import models
from django.conf import settings
from products.models import ProductVariant, Product
from django.core.validators import MinValueValidator, MaxValueValidator
from cloudinary.models import CloudinaryField



class Cart(models.Model):
    user       = models.OneToOneField(
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
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        return sum(
            item.subtotal
            for item in self.items.all()
            if item.is_available
        )
    @property
    def original_total(self):
        return sum(
            item.original_subtotal
            for item in self.items.all()
            if item.is_available
        )

    @property
    def total_discount(self):
        return self.original_total - self.total_price
    
    
    @property
    def has_out_of_stock(self):
        return any(not item.is_in_stock for item in self.items.all())

    @property
    def has_unavailable(self):
        return any(not item.is_available for item in self.items.all())


#  CART ITEM 

class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant  = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)

    custom_text  = models.CharField(max_length=100, blank=True, default='')
    custom_image = CloudinaryField('custom_image', blank=True, null=True)

    
    customization_charge = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

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
        from offers.utils import get_effective_price
    
        effective_price, _ = get_effective_price(self.variant)
        return (effective_price * self.quantity) + self.customization_charge

    @property
    def is_available(self):
        return (
            self.variant.is_active and
            self.variant.product.is_active and
            self.variant.product.category.is_active
        )
    @property
    def original_subtotal(self):
        return (self.variant.price * self.quantity) + self.customization_charge

    @property
    def discount_amount(self):
        return self.original_subtotal - self.subtotal
    
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


#  WISHLIST 

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


# WISHLIST ITEM

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    variant  = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['wishlist', 'variant']
        ordering        = ['-added_at']

    def __str__(self):
        return f"{self.variant} in {self.wishlist.user.email}'s wishlist"

    @property
    def is_available(self):
        return (
            self.variant.is_active and
            self.variant.product.is_active and
            self.variant.product.category.is_active
        )

    @property
    def primary_image(self):
        return self.variant.images.filter(is_primary=True).first() or self.variant.images.first()

    @property
    def product(self):
        return self.variant.product

    @property
    def min_price(self):
        
        return self.variant.price


#  REVIEW 
class Review(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
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
        unique_together = ['product', 'user']
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — {self.product.name} ({self.rating}★)"