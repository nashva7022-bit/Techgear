from decimal import ROUND_DOWN, Decimal
from django.utils import timezone


def get_effective_price(variant):

    today = timezone.now().date()
    best_discount = Decimal("0")

    # Check product offers
    for offer in variant.product.offers.all():
        if (
            offer.is_active
            and offer.start_date <= today <= offer.end_date
            and offer.discount_percent > best_discount
        ):
            best_discount = offer.discount_percent

    # Check category offers
    if variant.product.category:
        for offer in variant.product.category.offers.all():
            if (
                offer.is_active
                and offer.start_date <= today <= offer.end_date
                and offer.discount_percent > best_discount
            ):
                best_discount = offer.discount_percent

    if best_discount > 0:
        multiplier = (Decimal("100") - best_discount) / Decimal("100")
        effective_price = (variant.price * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        return effective_price, best_discount

    return variant.price, Decimal("0")
