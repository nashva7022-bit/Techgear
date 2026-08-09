import uuid

from cloudinary.models import CloudinaryField
from django.conf import settings
from django.db import models
from django.utils import timezone

# ORDER STATUS CHOICES

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("shipped", "Shipped"),
    ("out_for_delivery", "Out for Delivery"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
]

VALID_TRANSITIONS = {
    "pending": ["shipped", "cancelled"],
    "shipped": ["out_for_delivery"],
    "out_for_delivery": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

# ITEM STATUS CHOICES

ITEM_STATUS_CHOICES = [
    ("active", "Active"),
    ("cancelled", "Cancelled"),
    ("return_requested", "Return Requested"),
    ("returned", "Returned"),
    ("return_rejected", "Return Rejected"),
]

# PAYMENT METHOD CHOICES
PAYMENT_METHOD_CHOICES = [
    ("cod", "Cash on Delivery"),
    ("razorpay", "Razorpay"),
    ("wallet", "Wallet"),
    ("wallet_cod", "Wallet + Cash on Delivery"),
    ("wallet_razorpay", "Wallet + Razorpay"),
]


def generate_order_number():
    return "ORD-" + uuid.uuid4().hex[:8].upper()


# ORDER MODEL


class Order(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )
    order_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_number,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default="pending",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="cod",
    )

    shipping_full_name = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=15)
    shipping_address_line_1 = models.CharField(max_length=255)
    shipping_address_line_2 = models.CharField(max_length=255, blank=True, default="")
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100, default="India")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    wallet_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Amount paid from wallet"
    )
    coupon_code = models.CharField(max_length=30, blank=True, default="")
    coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount paid via COD or Razorpay",
    )
    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")

    # TIMESTAMPS
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.order_number} — {self.user.email if self.user else 'Deleted User'}"
        )

    @property
    def can_cancel(self):
        return self.status == "pending"

    @property
    def can_return(self):
        return self.status == "delivered"

    @property
    def shipping_address_display(self):
        parts = [
            self.shipping_address_line_1,
            self.shipping_address_line_2,
            self.shipping_city,
            self.shipping_state,
            self.shipping_postal_code,
            self.shipping_country,
        ]
        return ", ".join(p for p in parts if p)


# ORDER ITEM MODEL


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    # Snapshot fields
    product_name = models.CharField(max_length=150)
    variant_sku = models.CharField(max_length=50, blank=True, default="")
    device_model = models.CharField(max_length=100, blank=True, default="")
    case_type = models.CharField(max_length=50, blank=True, default="")
    color = models.CharField(max_length=50, blank=True, default="")
    color_code = models.CharField(max_length=7, blank=True, default="")
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="MRP per unit at time of purchase, before any offer discount",
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    # Customization snapshot
    custom_text = models.CharField(max_length=100, blank=True, default="")
    custom_image = CloudinaryField("custom_image", blank=True, null=True)

    customization_charge = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    # Item status
    item_status = models.CharField(
        max_length=20, choices=ITEM_STATUS_CHOICES, default="active"
    )
    cancellation_reason = models.TextField(blank=True, default="")
    return_reason = models.TextField(blank=True, default="")
    return_rejected_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.product_name} × {self.quantity} (Order: {self.order.order_number})"
        )

    @property
    def is_cancellable(self):
        return self.item_status == "active" and self.order.status == "pending"

    @property
    def is_returnable(self):
        return self.item_status == "active" and self.order.status == "delivered"

    @property
    def is_return_pending(self):
        return self.item_status == "return_requested"

    @property
    def is_return_rejected(self):
        return self.item_status == "return_rejected"


# ORDER STATUS LOG (ACTIVITY LOG)


class OrderStatusLog(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )

    old_status = models.CharField(max_length=20, blank=True, default="")
    new_status = models.CharField(max_length=20)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.order.order_number}: "
            f"{self.old_status or 'created'} → {self.new_status}"
        )
