from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db.models import Q, Min,Avg
from django.core.paginator import Paginator

from products.models import (
    Category, Product, ProductVariant,
    BRAND_CHOICES, CASE_TYPE_CHOICES
)
from .models import Cart, CartItem, Wishlist, WishlistItem


# ══════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════

def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart

def get_or_create_wishlist(user):
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


# ══════════════════════════════════════════
# PRODUCT LIST
# ══════════════════════════════════════════

@login_required
@never_cache
def product_list(request):
    search        = request.GET.get('search', '').strip()
    category_slug = request.GET.get('category', '').strip()
    brand         = request.GET.get('brand', '').strip()
    sort_by       = request.GET.get('sort', 'newest')
    min_price     = request.GET.get('min_price', '').strip()
    max_price     = request.GET.get('max_price', '').strip()

    products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
    ).select_related('category').prefetch_related(
        'variants__images',
        'variants__device_model',
    ).distinct()

    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(category__name__icontains=search) |
            Q(brand__icontains=search)
        )

    selected_category = None
    if category_slug:
        selected_category = Category.objects.filter(
            slug=category_slug, is_active=True
        ).first()
        if selected_category:
            products = products.filter(category=selected_category)

    if brand:
        products = products.filter(brand=brand)

    if min_price or max_price:
        try:
            qs = products.filter(variants__is_active=True)
            if min_price:
                qs = qs.filter(variants__price__gte=float(min_price))
            if max_price:
                qs = qs.filter(variants__price__lte=float(max_price))
            products = qs.distinct()
        except ValueError:
            pass

    if sort_by == 'price_asc':
        products = products.annotate(
            min_variant_price=Min('variants__price')
        ).order_by('min_variant_price')
    elif sort_by == 'price_desc':
        products = products.annotate(
            min_variant_price=Min('variants__price')
        ).order_by('-min_variant_price')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    else:
        products = products.order_by('-created_at')

    # Get user wishlist product ids for heart icon state
    wishlist     = get_or_create_wishlist(request.user)
    wishlist_ids = set(
        wishlist.items.values_list('product_id', flat=True)
    )

    paginator   = Paginator(products, 2)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'page_obj':          page_obj,
        'search':            search,
        'category_slug':     category_slug,
        'selected_category': selected_category,
        'brand':             brand,
        'sort_by':           sort_by,
        'min_price':         min_price,
        'max_price':         max_price,
        'categories':        Category.objects.filter(is_active=True).order_by('name'),
        'brand_choices':     BRAND_CHOICES,
        'wishlist_ids':      wishlist_ids,
        'has_filters':       any([search, category_slug, brand, min_price, max_price]),
    }
    return render(request, 'product_list.html', context)


# ══════════════════════════════════════════
# PRODUCT DETAIL
# ══════════════════════════════════════════

@login_required
@never_cache
def product_detail(request, slug):
    product = Product.objects.filter(
        slug=slug,
        is_active=True,
        category__is_active=True
    ).select_related('category').prefetch_related(
        'variants__images',
        'variants__device_model',
        'specifications',
    ).first()

    if not product:
        messages.error(request, "This product is no longer available.")
        return redirect('product_list')

    active_variants = product.variants.filter(
        is_active=True
    ).select_related('device_model').prefetch_related('images')

    selected_variant_id = request.GET.get('variant')
    selected_variant    = None

    if selected_variant_id:
        selected_variant = active_variants.filter(pk=selected_variant_id).first()

    if not selected_variant:
        selected_variant = active_variants.first()

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        category__is_active=True
    ).exclude(pk=product.pk).prefetch_related('variants__images')[:4]

    # Wishlist state for this product
    wishlist    = get_or_create_wishlist(request.user)
    in_wishlist = wishlist.items.filter(product=product).exists()

    case_type_choices = CASE_TYPE_CHOICES if product.is_customizable else []

    reviews = product.reviews.select_related('user').all()
    user_review = reviews.filter(user=request.user).first()
    
    # Average rating
    
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']

    context = {
        'product':           product,
        'active_variants':   active_variants,
        'selected_variant':  selected_variant,
        'related_products':  related_products,
        'specifications':    product.specifications.all(),
        'case_type_choices': case_type_choices,
        'in_wishlist':       in_wishlist,
        'reviews':     reviews,
        'user_review': user_review,
        'avg_rating':  round(avg_rating, 1) if avg_rating else None,
        'review_count': reviews.count(),
        'breadcrumbs': [
            {'name': 'Home',               'url': 'home'},
            {'name': 'Products',           'url': 'product_list'},
            {'name': product.category.name if product.category else 'Products', 'url': None},
            {'name': product.name,         'url': None},
        ],
    }
    return render(request, 'store/product_detail.html', context)


# ══════════════════════════════════════════
# CART VIEWS
# ══════════════════════════════════════════

@login_required
@never_cache
def cart_view(request):
    cart = get_or_create_cart(request.user)
    cart_items = cart.items.select_related(
        'variant__product__category',
        'variant__device_model',
    ).prefetch_related('variant__images')

    context = {
        'cart':       cart,
        'cart_items': cart_items,
    }
    return render(request, 'store/cart.html', context)


@login_required
@require_POST
def add_to_cart(request):
    variant_id = request.POST.get('variant_id')
    quantity   = int(request.POST.get('quantity', 1))

    variant = ProductVariant.objects.filter(
        pk=variant_id,
        is_active=True,
        product__is_active=True,
        product__category__is_active=True,
    ).select_related('product__category').first()

    if not variant:
        messages.error(request, "This product is no longer available.")
        return redirect('product_list')

    if variant.stock <= 0:
        messages.error(request, "Sorry, this item is out of stock.")
        return redirect('product_detail', slug=variant.product.slug)

    cart         = get_or_create_cart(request.user)
    custom_text  = request.POST.get('custom_text', '').strip()
    custom_image = request.FILES.get('custom_image')

    existing_item = None
    if not variant.product.is_customizable:
        existing_item = CartItem.objects.filter(
            cart=cart, variant=variant
        ).first()

    if existing_item:
        new_qty = existing_item.quantity + quantity
        if new_qty > variant.stock:
            messages.error(request, f"Only {variant.stock} units available in stock.")
            return redirect('product_detail', slug=variant.product.slug)
        if new_qty > 5:
            messages.error(request, "Maximum 5 of the same item allowed in cart.")
            return redirect('product_detail', slug=variant.product.slug)
        existing_item.quantity = new_qty
        existing_item.save()
        messages.success(request, "Cart updated.")
    else:
        quantity = min(quantity, 5)
        if quantity > variant.stock:
            messages.error(request, f"Only {variant.stock} units available in stock.")
            return redirect('product_detail', slug=variant.product.slug)

        cart_item = CartItem(cart=cart, variant=variant, quantity=quantity)
        if variant.product.is_customizable:
            if custom_text:
                cart_item.custom_text = custom_text
            if custom_image:
                cart_item.custom_image = custom_image
        cart_item.save()

        # Remove from wishlist when added to cart
        wishlist = get_or_create_wishlist(request.user)
        wishlist.items.filter(product=variant.product).delete()

        messages.success(request, "Item added to cart!")

    return redirect('cart')


@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(
        CartItem, pk=item_id, cart__user=request.user
    )
    action = request.POST.get('action')

    if action == 'increase':
        new_qty = cart_item.quantity + 1
        if new_qty > cart_item.variant.stock:
            messages.error(request, f"Only {cart_item.variant.stock} available in stock.")
            return redirect('cart')
        if new_qty > 5:
            messages.error(request, "Maximum 5 of the same item allowed.")
            return redirect('cart')
        cart_item.quantity = new_qty
        cart_item.save()

    elif action == 'decrease':
        if cart_item.quantity <= 1:
            cart_item.delete()
            messages.success(request, "Item removed from cart.")
            return redirect('cart')
        cart_item.quantity -= 1
        cart_item.save()

    return redirect('cart')


@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(
        CartItem, pk=item_id, cart__user=request.user
    )
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('cart')


# ══════════════════════════════════════════
# WISHLIST VIEWS
# ══════════════════════════════════════════

@login_required
@never_cache
def wishlist_view(request):
    wishlist = get_or_create_wishlist(request.user)
    items    = wishlist.items.select_related(
        'product__category'
    ).prefetch_related(
        'product__variants__images'
    )
    context = {
        'wishlist': wishlist,
        'items':    items,
    }
    return render(request, 'store/wishlist.html', context)


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    """
    Add to wishlist if not in it.
    Remove from wishlist if already in it.
    Returns to the page user came from.
    """
    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
        category__is_active=True
    )
    wishlist = get_or_create_wishlist(request.user)

    item, created = WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product=product
    )
    if not created:
        # Already in wishlist — remove it
        item.delete()
        messages.success(request, f'"{product.name}" removed from wishlist.')
    else:
        messages.success(request, f'"{product.name}" added to wishlist.')

    # Go back to where user came from
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', 'wishlist')
    return redirect(next_url)


@login_required
@require_POST
def move_to_cart(request, item_id):
    """
    Moves a wishlist item to cart.
    Uses the first active variant of the product.
    Removes from wishlist after adding to cart.
    """
    wishlist_item = get_object_or_404(
        WishlistItem,
        pk=item_id,
        wishlist__user=request.user
    )
    product = wishlist_item.product

    # Check product still available
    if not product.is_active or not product.category.is_active:
        messages.error(request, "This product is no longer available.")
        wishlist_item.delete()
        return redirect('wishlist')

    # Get first active variant
    variant = product.variants.filter(is_active=True, stock__gt=0).first()

    if not variant:
        messages.error(request, "This product is currently out of stock.")
        return redirect('wishlist')

    # Add to cart
    cart          = get_or_create_cart(request.user)
    existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()

    if existing_item:
        new_qty = existing_item.quantity + 1
        if new_qty <= min(5, variant.stock):
            existing_item.quantity = new_qty
            existing_item.save()
        else:
            messages.error(request, "Maximum quantity reached for this item.")
            return redirect('wishlist')
    else:
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    # Remove from wishlist
    wishlist_item.delete()
    messages.success(request, f'"{product.name}" moved to cart.')
    return redirect('cart')


@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    """Remove a single item from wishlist."""
    wishlist_item = get_object_or_404(
        WishlistItem,
        pk=item_id,
        wishlist__user=request.user
    )
    name = wishlist_item.product.name
    wishlist_item.delete()
    messages.success(request, f'"{name}" removed from wishlist.')
    return redirect('wishlist')