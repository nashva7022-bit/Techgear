from django.conf import settings
from django.db import models
from django.utils import timezone

DISCOUNT_TYPE_CHOICES = [
    ("percentage", "Percentage"),
    ("fixed", "Fixed Amount"),
]


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    discount_type = models.CharField(
        max_length=20, choices=DISCOUNT_TYPE_CHOICES, default="percentage"
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_cap = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Only applies to percentage discounts. Leave blank for no cap.",
    )
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total times this coupon can be used across all users. Leave blank for unlimited.",
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    @property
    def times_used(self):
        return self.usages.count()

    @property
    def is_currently_valid(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if not (self.start_date <= today <= self.end_date):
            return False
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False
        return True


class CouponUsage(models.Model):

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coupon_usages"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_usage",
    )
    used_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ["coupon", "user"]  # enforces one-use-per-user at DB level

    def __str__(self):
        return f"{self.coupon.code} used by {self.user.email}"
