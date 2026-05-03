from django.db import models

# Create your models here.
# store/models.py

from django.db import models
from django.conf import settings
from products.models import ProductVariant


class Cart(models.Model):
    """
    WHY: One cart per user.
    We create this automatically when user
    first adds something to cart.
    """
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
        """Total number of items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        """Total price of all items in cart."""
        return sum(item.subtotal for item in self.items.all())

    @property
    def has_out_of_stock(self):
        """
        WHY: We need to know if cart has
        out of stock items before checkout.
        If yes → disable checkout button.
        """
        return any(
            item.quantity > item.variant.stock
            for item in self.items.all()
        )


class CartItem(models.Model):
    cart     = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    variant  = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)

    # ── CUSTOMIZATION FIELDS ──────────────────
    # WHY: Only used when category.is_customizable = True
    # Phone Cases and Laptop Skins only.
    # Blank for normal products like grips/protectors.
    custom_text  = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Custom text to print on the product.'
    )
    custom_image = models.ImageField(
        upload_to='cart_custom_images/',
        blank=True,
        null=True,
        help_text='Custom image to print on the product.'
    )
    # ─────────────────────────────────────────

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        variant = self.variant
        product = variant.product

        # Build variant description dynamically
        parts = []

        # Device model — always shown for all categories
        if variant.device_model:
            parts.append(variant.device_model.name)

        # Case type — ONLY for customizable categories
        # (Phone Cases, Laptop Skins)
        # Not shown for Phone Grips, Screen Protectors
        if variant.case_type and product.is_customizable:
            parts.append(variant.get_case_type_display())

        # Colour — always shown
        parts.append(variant.get_color_display())

        variant_desc = ' — '.join(parts)
        return f"{product.name} ({variant_desc}) × {self.quantity}"

    @property
    def subtotal(self):
        return self.variant.price * self.quantity

    @property
    def is_available(self):
        """
        WHY: Product or category may have been
        deactivated AFTER user added to cart.
        We check all 3 levels:
        variant → product → category
        """
        return (
            self.variant.is_active and
            self.variant.product.is_active and
            self.variant.product.category.is_active
        )

    @property
    def is_in_stock(self):
        """
        WHY: Stock may have reduced after
        user added item to cart.
        """
        return self.variant.stock >= self.quantity

    @property
    def max_quantity(self):
        """
        WHY: Cap at 5 OR available stock,
        whichever is lower.
        Prevents user buying more than available.
        """
        return min(5, self.variant.stock)

    @property
    def is_customizable(self):
        """
        WHY: Template uses this to decide
        whether to show custom text/image
        fields for this cart item.
        """
        return self.variant.product.is_customizable

    @property
    def variant_display(self):
        """
        WHY: Clean readable variant description
        for use in templates.

        Normal:       iPhone 15 Pro — Black
        Customizable: iPhone 15 Pro — Slim Fit — Black
        """
        parts = []
        variant = self.variant
        product = variant.product

        if variant.device_model:
            parts.append(variant.device_model.name)

        # Case type only for customizable categories
        if variant.case_type and product.is_customizable:
            parts.append(variant.get_case_type_display())

        parts.append(variant.get_color_display())

        return ' — '.join(parts)