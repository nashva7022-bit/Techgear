from decimal import ROUND_DOWN, Decimal

from django.utils import timezone

from .models import Coupon, CouponUsage


def validate_coupon(code, user, order_subtotal):

    code = code.strip().upper()

    coupon = Coupon.objects.filter(code__iexact=code).first()
    if not coupon:
        return None, "Invalid coupon code."

    today = timezone.now().date()

    if not coupon.is_active:
        return None, "This coupon is no longer active."

    if today < coupon.start_date:
        return None, "This coupon is not yet active."

    if today > coupon.end_date:
        return None, "This coupon has expired."

    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        return None, "This coupon has reached its usage limit."

    if CouponUsage.objects.filter(coupon=coupon, user=user).exists():
        return None, "You have already used this coupon."

    if order_subtotal < coupon.min_order_amount:
        return (
            None,
            f"Minimum order amount of ₹{coupon.min_order_amount} required for this coupon.",
        )

    return coupon, None


def calculate_coupon_discount(coupon, order_subtotal):

    if coupon.discount_type == "percentage":
        discount = (order_subtotal * coupon.discount_value) / Decimal("100")
        if coupon.max_discount_cap is not None:
            discount = min(discount, coupon.max_discount_cap)
    else:
        discount = coupon.discount_value

    discount = min(discount, order_subtotal)

    return discount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
