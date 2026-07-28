from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db.models import Q, Min,Avg
from django.core.paginator import Paginator
from django.http import JsonResponse   
import json
from django.conf import settings
from offers.utils import get_effective_price
from orders.models import OrderItem
from products.models import (
    Category, Product, ProductVariant,
    BRAND_CHOICES, CASE_TYPE_CHOICES
)
from .models import Cart, CartItem, Wishlist, WishlistItem,Review
#cart creating helper

def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart

def get_or_create_wishlist(user):
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist
#for nav display

def _cart_count(user):
    try:
        return user.cart.total_items
    except Exception:
        return 0

# PRODUCT LIST


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

 #to highlight  
    wishlist     = get_or_create_wishlist(request.user)
    wishlist_ids = set(
        wishlist.items.values_list('variant__product_id', flat=True)
    )
    

    
    paginator = Paginator(products, settings.PRODUCTS_PER_PAGE)
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





# PRODUCT DETAIL 

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

    variants_data = []
    for v in active_variants:
        images = [img.image.url for img in v.images.all()]
        eff_price, disc_pct = get_effective_price(v)
        variants_data.append({
            'id': v.pk,
            'device_model_id': v.device_model.pk if v.device_model else None,
            'device_model': v.device_model.name if v.device_model else '',
            'case_type': v.case_type or '',
            'case_type_label': v.get_case_type_display() if v.case_type else '',
            'color': v.color,
            'color_label': v.get_color_display(),
            'color_code': v.color_code,
            'price': str(v.price),
            #offer
            'effective_price': str(eff_price),
            'discount_pct': str(disc_pct),
            'stock': v.stock,
            'sku': v.sku or '',
            'images': images,
            'primary_image': images[0] if images else '',
        })
    selected_variant_id = request.GET.get('variant')
    selected_variant    = None

    if selected_variant_id:
        selected_variant = active_variants.filter(pk=selected_variant_id).first()

    if not selected_variant:
        selected_variant = active_variants.first()

    #you may also like
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        category__is_active=True
    ).exclude(pk=product.pk).prefetch_related('variants__images')[:4]

    wishlist    = get_or_create_wishlist(request.user)
    in_wishlist = wishlist.items.filter(variant=selected_variant).exists()#checks like selected variant is already in wish

    case_type_choices = CASE_TYPE_CHOICES if product.is_customizable else []

    reviews     = product.reviews.select_related('user').all()
    user_review = reviews.filter(user=request.user).first()
    avg_rating  = reviews.aggregate(Avg('rating'))['rating__avg']

    context = {
        'product':           product,
        'active_variants':   active_variants,
        'selected_variant':  selected_variant,
        'variants_data':     json.dumps(variants_data), 
        'related_products':  related_products,
        'specifications':    product.specifications.all(),
        'case_type_choices': case_type_choices,
        'in_wishlist':       in_wishlist,
        'reviews':           reviews,
        'user_review':       user_review,
        'avg_rating':        round(avg_rating, 1) if avg_rating else None,
        'review_count':      reviews.count(),
        'from_wishlist': request.GET.get('from_wishlist', False),
        'breadcrumbs': [#shows nav path
            {'name': 'Home',     'url': 'home'},
            {'name': 'Products', 'url': 'product_list'},
            {'name': product.category.name if product.category else 'Products', 'url': None},
            {'name': product.name, 'url': None},
        ],
    }
    return render(request, 'product_detail.html', context)


# CART VIEWS


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
    return render(request, 'cart.html', context)


@login_required
@require_POST

def add_to_cart(request):
    variant_id = request.POST.get('variant_id')
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    quantity = max(1, quantity)
    
    is_ajax  = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    variant = ProductVariant.objects.filter(
        pk=variant_id,
        is_active=True,
        product__is_active=True,
        product__category__is_active=True,
    ).select_related('product__category').first()

    if not variant:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'This product is no longer available.'})
        messages.error(request, "This product is no longer available.")
        return redirect('product_list')

    if variant.stock <= 0:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Sorry, this item is out of stock.'})
        messages.error(request, "Sorry, this item is out of stock.")
        return redirect('product_detail', slug=variant.product.slug)

    cart         = get_or_create_cart(request.user)
    custom_text  = request.POST.get('custom_text', '').strip()
    custom_image = request.FILES.get('custom_image')
    has_customization = bool(custom_text or custom_image)

    
    customization_charge = 0
    if has_customization and variant.product.is_customizable:
        from admin_panel.models import SiteSettings
        customization_charge = SiteSettings.get().customization_fee

   
    existing_item = CartItem.objects.filter(
        cart=cart,
        variant=variant,
        custom_text='',
        custom_image=None,
    ).first() if not has_customization else None

    if existing_item:
        new_qty = existing_item.quantity + quantity
        if new_qty > variant.stock:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': f'Only {variant.stock} units available in stock.'})
            messages.error(request, f"Only {variant.stock} units available in stock.")
            return redirect('product_detail', slug=variant.product.slug)

        if new_qty > 5:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Maximum 5 of the same item allowed in cart.'})
            messages.error(request, "Maximum 5 of the same item allowed in cart.")
            return redirect('product_detail', slug=variant.product.slug)

        existing_item.quantity = new_qty
        existing_item.save()
       
        wishlist = get_or_create_wishlist(request.user)
        wishlist.items.filter(variant__product=variant.product).delete()

        if is_ajax:
            return JsonResponse({
                'ok':             True,
                'message':        'Cart updated!',
                'cart_count':     _cart_count(request.user),
                'wishlist_count': wishlist.items.count(),
            })
        messages.success(request, "Cart updated.")

    else:
        quantity = min(quantity, 5)
        if quantity > variant.stock:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': f'Only {variant.stock} units available in stock.'})
            messages.error(request, f"Only {variant.stock} units available in stock.")
            return redirect('product_detail', slug=variant.product.slug)
        
        #creates cart obj

        cart_item = CartItem(
            cart=cart,
            variant=variant,
            quantity=quantity,
            customization_charge=customization_charge, 
        )
        if variant.product.is_customizable:
            if custom_text:
                cart_item.custom_text = custom_text
            if custom_image:
                cart_item.custom_image = custom_image
        cart_item.save()
         

        wishlist = get_or_create_wishlist(request.user)
        wishlist.items.filter(variant__product=variant.product).delete()

        if is_ajax:
            return JsonResponse({
                'ok':             True,
                'message':        'Item added to cart!',
                'cart_count':     _cart_count(request.user),
                'wishlist_count': wishlist.items.count(),
            })
        messages.success(request, "Item added to cart!")

    return redirect('cart')

@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(
        CartItem, pk=item_id, cart__user=request.user
    )
    action  = request.POST.get('action')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if action == 'increase':
        new_qty = cart_item.quantity + 1
        if new_qty > cart_item.variant.stock:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': f'Only {cart_item.variant.stock} available in stock.'})
            messages.error(request, f"Only {cart_item.variant.stock} available in stock.")
            return redirect('cart')
        if new_qty > 5:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Maximum 5 of the same item allowed.'})
            messages.error(request, "Maximum 5 of the same item allowed.")
            return redirect('cart')
        cart_item.quantity = new_qty
        cart_item.save()

    elif action == 'decrease':
        if cart_item.quantity <= 1:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Minimum quantity is 1. Remove item to delete.'})
            return redirect('cart')
        cart_item.quantity -= 1
        cart_item.save()

    if is_ajax:
        cart        = cart_item.cart
        
        subtotal    = cart_item.subtotal
        
        all_items = cart.items.select_related('variant').all()

        cart_total = sum(i.subtotal for i in all_items)

        # Re-validate coupon if one is applied
        applied_coupon_data = request.session.get("applied_coupon")
        if applied_coupon_data:
            from coupons.models import Coupon
            from coupons.utils import validate_coupon
            
            try:
                coupon = Coupon.objects.get(code=applied_coupon_data["code"])
                _, error = validate_coupon(coupon.code, request.user, cart_total)
                if error:
                    # Coupon no longer valid, remove it
                    request.session.pop("applied_coupon", None)
                    request.session.modified = True
            except Coupon.DoesNotExist:
                request.session.pop("applied_coupon", None)
                request.session.modified = True


        original_total = sum(i.original_subtotal for i in all_items)

        customization_total = sum(
            i.customization_charge for i in all_items
        )

        original_product_total = original_total - customization_total

        discount_total = original_total - cart_total 
        total_items = sum(i.quantity for i in all_items)

        return JsonResponse({
            'ok': True,
            'deleted': False,
            'quantity': cart_item.quantity,
            'subtotal': float(subtotal),
            'cart_total': float(cart_total),

            'original_total': float(original_total),
            'original_product_total': float(original_product_total),
            'discount_total': float(discount_total),

            'total_items': total_items,
        })
    return redirect('cart')



@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(
        CartItem, pk=item_id, cart__user=request.user
    )
    
    cart_item.delete()
    
    # Re-validate coupon after item removal
    applied_coupon_data = request.session.get("applied_coupon")
    if applied_coupon_data:
        from coupons.models import Coupon
        from coupons.utils import validate_coupon
        from decimal import Decimal
        
        cart = request.user.cart
        if cart.items.exists():
            cart_total = Decimal(str(cart.total_price))
            
            try:
                coupon = Coupon.objects.get(code=applied_coupon_data["code"])
                _, error = validate_coupon(coupon.code, request.user, cart_total)
                if error:
                    request.session.pop("applied_coupon", None)
                    request.session.modified = True
                    messages.info(request, "Coupon removed — cart no longer qualifies.")
            except Coupon.DoesNotExist:
                request.session.pop("applied_coupon", None)
                request.session.modified = True
    
    messages.success(request, "Item removed from cart.")
    return redirect('cart')

@login_required
@require_POST
def update_cart_customisation(request, item_id):
    cart_item = get_object_or_404(
        CartItem, pk=item_id, cart__user=request.user
    )

    if not cart_item.variant.product.is_customizable:
        messages.error(request, "This item cannot be customised.")
        return redirect('cart')

    custom_text  = request.POST.get('custom_text', '').strip()
    custom_image = request.FILES.get('custom_image')
    remove_image = request.POST.get('remove_custom_image') == '1'

    cart_item.custom_text = custom_text

    if remove_image:
        cart_item.custom_image = None
    elif custom_image:
        cart_item.custom_image = custom_image

    
    has_customization = bool(cart_item.custom_text) or bool(cart_item.custom_image)

    if has_customization:
        from admin_panel.models import SiteSettings
        cart_item.customization_charge = SiteSettings.get().customization_fee
    else:
        cart_item.customization_charge = 0

    cart_item.save()
    messages.success(request, "Personalisation updated.")
    return redirect('cart')


# WISHLIST VIEWS


@login_required
@never_cache
def wishlist_view(request):
    wishlist = get_or_create_wishlist(request.user)
    items    = wishlist.items.select_related(
        'variant__product__category',
        'variant__device_model',
    ).prefetch_related('variant__images')
    context = {
        'wishlist': wishlist,
        'items':    items,
    }
    return render(request, 'wishlist.html', context)


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    is_ajax    = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    variant_id = request.POST.get('variant_id')

    product = get_object_or_404(
        Product,
        pk=product_id,
        is_active=True,
        category__is_active=True
    )

    
    variant = ProductVariant.objects.filter(
        pk=variant_id,
        is_active=True,
        product=product,
    ).first()

    
    if not variant:
        variant = product.variants.filter(is_active=True).first()

    
    if not variant:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'No active variant found.'})
        messages.error(request, 'No active variant found.')
        return redirect('product_list')

    wishlist = get_or_create_wishlist(request.user)

    item = wishlist.items.filter(variant=variant).first()
    if item:
        item.delete()
        in_wishlist = False
        msg = f'"{product.name}" removed from wishlist.'
    else:
        WishlistItem.objects.create(wishlist=wishlist, variant=variant)
        in_wishlist = True
        msg = f'"{product.name}" added to wishlist.'

    if is_ajax:
        return JsonResponse({
            'ok':          True,
            'in_wishlist': in_wishlist,
            'message':     msg,
            'wishlist_count': wishlist.items.count(),
        })

    messages.success(request, msg)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', 'wishlist')
    return redirect(next_url)


@login_required
@require_POST
def move_to_cart(request, item_id):
    wishlist_item = get_object_or_404(
        WishlistItem,
        pk=item_id,
        wishlist__user=request.user
    )
    variant = wishlist_item.variant
    product = variant.product

    
    if not product.is_active or not product.category.is_active or not variant.is_active:
        messages.error(request, "This product is no longer available.")
        wishlist_item.delete()
        return redirect('wishlist')


    if variant.stock <= 0:
        messages.error(request, f'"{product.name}" is currently out of stock.')
        return redirect('wishlist')

 
    cart          = get_or_create_cart(request.user)
    existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()

    if existing_item:
        new_qty = existing_item.quantity + 1
        if new_qty > min(5, variant.stock):
            messages.error(request, "Maximum quantity reached for this item.")
            return redirect('wishlist')
        existing_item.quantity = new_qty
        existing_item.save()
    else:
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    
    wishlist_item.delete()
    messages.success(request, f'"{product.name}" moved to cart.')
    return redirect('wishlist')

@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    
    wishlist_item = get_object_or_404(
        WishlistItem,
        pk=item_id,
        wishlist__user=request.user
    )
    name = wishlist_item.product.name
    wishlist_item.delete()
    messages.success(request, f'"{name}" removed from wishlist.')
    return redirect('wishlist')

from .models import Cart, CartItem, Wishlist, WishlistItem, Review
from orders.models import Order, OrderItem

@login_required
@require_POST
def submit_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)

    
    has_delivered = OrderItem.objects.filter(
        order__user    = request.user,
        order__status  = 'delivered',
        variant__product = product,
        item_status    = 'active',
    ).exists()

    if not has_delivered:
        messages.error(request, "You can only review products you have purchased and received.")
        return redirect('product_detail', slug=product.slug)

    rating  = request.POST.get('rating', '').strip()
    comment = request.POST.get('comment', '').strip()

    if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
        messages.error(request, "Please select a rating between 1 and 5.")
        return redirect('product_detail', slug=product.slug)

   
    Review.objects.update_or_create(
        product = product,
        user    = request.user,
        defaults = {
            'rating':  int(rating),
            'comment': comment,
        }
    )

    messages.success(request, "Your review has been submitted!")
    return redirect('product_detail', slug=product.slug)