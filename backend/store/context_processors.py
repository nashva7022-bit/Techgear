from .models import Cart, Wishlist
from products.models import Category

def cart_wishlist(request):
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    if not request.user.is_authenticated:
        return {'cart_count': 0, 'wishlist_count': 0, 'categories': categories}
    
    try:
        cart_count = request.user.cart.total_items
    except Exception:
        cart_count = 0

    try:
        wishlist_count = request.user.wishlist.total_items
    except Exception:
        wishlist_count = 0

    return {
        'cart_count':     cart_count,
        'wishlist_count': wishlist_count,
        'categories':     categories,
    }