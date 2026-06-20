from django.utils import timezone
from decimal import Decimal, ROUND_DOWN

from .models import ProductOffer, CategoryOffer


def get_effective_price(variant):
   
    today         = timezone.now().date()
    best_discount = Decimal('0')

    # Check product offer
    try:
        offer = variant.product.offer
        if (offer.is_active and
                offer.start_date <= today <= offer.end_date and
                offer.discount_percent > best_discount):
            best_discount = offer.discount_percent
    except ProductOffer.DoesNotExist:
        pass

    # Check category offer
    try:
        offer = variant.product.category.offer
        if (offer.is_active and
                offer.start_date <= today <= offer.end_date and
                offer.discount_percent > best_discount):
            best_discount = offer.discount_percent
    except CategoryOffer.DoesNotExist:
        pass

    if best_discount > 0:
        multiplier      = (Decimal('100') - best_discount) / Decimal('100')
        effective_price = (variant.price * multiplier).quantize(
            Decimal('0.01'), rounding=ROUND_DOWN
        )
        return effective_price, best_discount

    return variant.price, Decimal('0')