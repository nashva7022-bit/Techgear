from django import template
from offers.utils import get_effective_price

register = template.Library()

@register.simple_tag
def effective_price(variant):
    price, _ = get_effective_price(variant)
    return price

@register.simple_tag
def discount_percent(variant):
    _, percent = get_effective_price(variant)
    return percent