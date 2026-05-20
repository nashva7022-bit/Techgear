from django.shortcuts import render
from django.conf import settings

# Create your views here.
# views.py handles what happens when a user visits a URL.
# It receives the request, does some logic, and returns a response.
# We keep views THIN — they just receive, validate, call services, and respond.
# The heavy logic lives in services.py, not here.

from django.shortcuts import render, redirect, get_object_or_404
# render        — takes a template and context, returns an HTML response
# redirect      — sends user to a different URL
# get_object_or_404 — fetches a DB object, shows 404 page if not found
# Without these, we'd have to write much more code for basic responses.

from django.contrib.auth.decorators import login_required
# Protects views so only logged-in users can access them.
# Without this, anyone (even not logged in) could visit /checkout/ or /orders/.

from django.views.decorators.http import require_POST
# Makes sure certain views only accept POST requests, not GET.
# Without this, someone could trigger a cancel just by visiting a URL in browser.

from django.views.decorators.cache import never_cache
# Tells the browser never to cache these pages.
# Without this, user could press Back after placing order and see
# the checkout page again from cache — very confusing.

from django.contrib import messages
# Django's built-in flash message system.
# Lets us show "Order placed!" or "Error: out of stock" after a redirect.
# Without this, we'd have no way to show feedback after redirecting.

from django.http import JsonResponse
# Used for AJAX responses — returns JSON instead of HTML.
# Without this, AJAX calls from JavaScript would get HTML back, which is useless.

from django.db.models import Q
# Lets us do complex database queries like search across multiple fields.
# Without this, we can only filter by one field at a time.

from django.core.paginator import Paginator
# Splits a long list into pages (10 orders per page, etc.)
# Without this, if a user has 500 orders, all 500 load at once — very slow.

from .models import Order, OrderItem, OrderStatusLog
# Our order models. Without these imports we can't query orders at all.


from django.http import HttpResponse
from django.template.loader import render_to_string
from .services import (
    place_cod_order,
    cancel_order,
    cancel_order_item,
    return_order_item,
)
# Our business logic functions from services.py.
# Without these, we'd have to put all that logic directly in views — messy.

from store.models import Cart
# We need the Cart to read items for checkout and clear it after order is placed.

from users.models import Address
# We need Address so we can show the user's saved addresses on checkout page
# and let them pick one.

from users.forms import AddressForm
# The same address form used in profile page.
# We reuse it on the checkout page so user can add a new address inline
# without going to the profile page — as your mentor instructed.


# ── CHECKOUT VIEW ─────────────────────────────────────────────────────────────

@login_required
@never_cache
def checkout(request):
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    # Evaluate once as a list — used everywhere below
    cart_items = list(
        cart.items.select_related(
            'variant__product__category',
            'variant__device_model',
        ).prefetch_related('variant__images')
    )

    addresses    = request.user.addresses.all().order_by('-is_default', '-created_at')
    address_form = AddressForm()

    # ── POST ──
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_address':
            address_form = AddressForm(request.POST)
            if address_form.is_valid():
                new_address      = address_form.save(commit=False)
                new_address.user = request.user
                new_address.save()
                if request.user.addresses.count() == 1:
                    new_address.is_default = True
                    new_address.save(update_fields=['is_default'])
                return JsonResponse({
                    'ok':      True,
                    'message': 'Address added successfully.',
                    'address': {
                        'id':         new_address.pk,
                        'label':      new_address.address_label,
                        'name':       new_address.full_name,
                        'line1':      new_address.address_line_1,
                        'line2':      new_address.address_line_2 or '',
                        'city':       new_address.city,
                        'state':      new_address.state,
                        'postal':     new_address.postal_code,
                        'country':    new_address.country,
                        'phone':      new_address.phone,
                        'is_default': new_address.is_default,
                    }
                })
            else:
                return JsonResponse({'ok': False, 'errors': address_form.errors}, status=400)

        elif action == 'edit_address':
            address_id   = request.POST.get('editing_address_id')
            address      = get_object_or_404(Address, pk=address_id, user=request.user)
            address_form = AddressForm(request.POST, instance=address)
            if address_form.is_valid():
                address_form.save()
                address.refresh_from_db()
                return JsonResponse({
                    'ok':      True,
                    'message': 'Address updated.',
                    'address': {
                        'id':         address.pk,
                        'label':      address.address_label,
                        'name':       address.full_name,
                        'line1':      address.address_line_1,
                        'line2':      address.address_line_2 or '',
                        'city':       address.city,
                        'state':      address.state,
                        'postal':     address.postal_code,
                        'country':    address.country,
                        'phone':      address.phone,
                        'is_default': address.is_default,
                    }
                })
            else:
                return JsonResponse({'ok': False, 'errors': address_form.errors}, status=400)

        elif action == 'place_order':
            address_id = request.POST.get('selected_address')
            if not address_id:
                messages.error(request, "Please select a delivery address.")
                return redirect('orders:checkout')
            address = get_object_or_404(Address, pk=address_id, user=request.user)
            try:
                order = place_cod_order(
                    user    = request.user,
                    cart    = cart,
                    address = address,
                )
                return redirect('orders:order_success', order_number=order.order_number)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('orders:checkout')

    # ── GET — calculate totals only when rendering the page ──
    subtotal       = sum(item.variant.discounted_price * item.quantity for item in cart_items)
    original_total = sum(item.variant.price * item.quantity for item in cart_items)
    discount_amount = original_total - subtotal
    shipping_charge = 0
    total_amount    = subtotal + shipping_charge

    context = {
        'cart':            cart,
        'cart_items':      cart_items,
        'addresses':       addresses,
        'address_form':    address_form,
        'subtotal':        subtotal,
        'discount_amount': discount_amount,
        'shipping_charge': shipping_charge,
        'total_amount':    total_amount,
        'original_total':  original_total,
    }
    return render(request, 'orders/checkout.html', context)

# ── ORDER SUCCESS VIEW ────────────────────────────────────────────────────────

@login_required
@never_cache
def order_success(request, order_number):
    # Shows the "Thank you for your order!" page.
    # order_number comes from the URL — e.g. /orders/success/ORD-A3F2B1C4/

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    # Fetches the order and checks it belongs to the logged-in user.
    # Without user=request.user, someone could visit another person's
    # success page by guessing the order number.

    context = {
        'order': order,
    }
    return render(request, 'orders/order_success.html', context)


# ── USER ORDER LIST ───────────────────────────────────────────────────────────

@login_required
@never_cache
def order_list(request):
    # Shows the user's full order history, newest first.

    search  = request.GET.get('search', '').strip()
    # Lets user search orders by order number.
    # .strip() removes accidental spaces around the search term.

    orders = Order.objects.filter(
        user = request.user
    ).prefetch_related('items')
    # Only fetch THIS user's orders — never show other users' orders.
    # prefetch_related('items') loads all order items in one extra query
    # instead of one query per order — much faster.

    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(items__product_name__icontains=search)
        ).distinct()
        # Search by order number OR product name inside the order.
        # .distinct() prevents duplicate orders appearing when multiple
        # items in the same order match the search.
        # Without distinct(), an order with 3 matching items would show 3 times.

    # orders are already ordered newest first because of Meta ordering in model.

    paginator = Paginator(orders, settings.ORDERS_PER_PAGE)
    # Show 10 orders per page.
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
    # get_page() handles invalid page numbers gracefully —
    # if someone passes page=999 and there are only 2 pages, it shows last page.
    # Without paginator, all orders load at once — slow for users with many orders.

    context = {
        'page_obj': page_obj,
        'search':   search,
    }
    return render(request, 'orders/order_list.html', context)


# ── USER ORDER DETAIL ─────────────────────────────────────────────────────────

@login_required
@never_cache
def order_detail(request, order_number):
    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    items = order.items.select_related('variant').prefetch_related('variant__images')
    status_logs = order.status_logs.all()

    # Get product IDs the user has already reviewed
    from store.models import Review
    reviewed_product_ids = set(
        Review.objects.filter(user=request.user).values_list('product_id', flat=True)
    )

    context = {
        'order':                order,
        'items':                items,
        'status_logs':          status_logs,
        'reviewed_product_ids': reviewed_product_ids,
    }
    return render(request, 'orders/order_detail.html', context)

# ── CANCEL ENTIRE ORDER ───────────────────────────────────────────────────────

@login_required
@require_POST
def cancel_order_view(request, order_number):
    # Cancels the entire order.
    # require_POST — only works with POST, not GET.
    # Without require_POST, user could cancel an order just by visiting a URL.

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    # Security — order must belong to logged-in user.

    reason = request.POST.get('reason', '').strip()
    # Optional cancellation reason typed by the user.

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    # Check if this is an AJAX request from JavaScript or a normal form POST.
    # We respond differently — JSON for AJAX, redirect for normal POST.

    try:
        cancel_order(
            order        = order,
            cancelled_by = request.user,
            reason       = reason,
        )
        # Calls our service function. It validates the status transition,
        # cancels all items, restores stock, and logs the change.

        if is_ajax:
            return JsonResponse({
                'ok':      True,
                'message': 'Order cancelled successfully.',
                'status':  'cancelled',
            })
        messages.success(request, "Your order has been cancelled.")
        return redirect('orders:order_detail', order_number=order_number)

    except ValueError as e:
        # cancel_order raises ValueError if cancellation is not allowed
        # (e.g. order is already shipped).
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('orders:order_detail', order_number=order_number)


# ── CANCEL SINGLE ITEM ────────────────────────────────────────────────────────

@login_required
@require_POST
def cancel_item_view(request, order_number, item_id):
    # Cancels just one item from the order.

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    # First verify the order belongs to this user.
    # Without this, someone could cancel items from other users' orders.

    item = get_object_or_404(
        OrderItem,
        pk    = item_id,
        order = order,
    )
    # Then verify the item belongs to this order.
    # order=order ensures the item is from THIS order, not some other order.
    # Without this check, user could pass any item_id and cancel it.

    reason  = request.POST.get('reason', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        cancel_order_item(
            order_item   = item,
            cancelled_by = request.user,
            reason       = reason,
        )

        if is_ajax:
            return JsonResponse({
                'ok':      True,
                'message': f'"{item.product_name}" has been cancelled.',
                'status':  'cancelled',
            })
        messages.success(request, f'"{item.product_name}" has been cancelled.')
        return redirect('orders:order_detail', order_number=order_number)

    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('orders:order_detail', order_number=order_number)


# ── RETURN SINGLE ITEM ────────────────────────────────────────────────────────

@login_required
@require_POST
def return_item_view(request, order_number, item_id):
    # Returns one item from a delivered order.
    # Reason is MANDATORY for returns — enforced here and in services.py.

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )

    item = get_object_or_404(
        OrderItem,
        pk    = item_id,
        order = order,
    )

    reason  = request.POST.get('reason', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Enforce mandatory reason for returns.
    if not reason:
        if is_ajax:
            return JsonResponse(
                {'ok': False, 'error': 'Please provide a reason for the return.'},
                status=400,
            )
        messages.error(request, "Please provide a reason for the return.")
        return redirect('orders:order_detail', order_number=order_number)
    # We check this here in the view AND in services.py.
    # Defense in depth — two layers of validation means it can never slip through.

    try:
        return_order_item(
            order_item   = item,
            returned_by  = request.user,
            reason       = reason,
        )

        if is_ajax:
            return JsonResponse({
                'ok':      True,
                'message': f'Return request for "{item.product_name}" submitted.',
                'status':  'returned',
            })
        messages.success(request, f'Return request for "{item.product_name}" submitted.')
        return redirect('orders:order_detail', order_number=order_number)

    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('orders:order_detail', order_number=order_number)


# ── PDF INVOICE DOWNLOAD ──────────────────────────────────────────────────────

@login_required
def download_invoice(request, order_number):
    # Generates and returns a PDF invoice for the order.
    # This is a normal GET request — user clicks "Download Invoice" link.
    # No AJAX needed here — browser handles file downloads natively.

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    # Security — only the order owner can download the invoice.

    # Only allow invoice download for delivered orders.
    if order.status not in ['delivered', 'cancelled']:
        messages.error(request, "Invoice is only available for delivered or cancelled orders.")
        return redirect('orders:order_detail', order_number=order_number)
    # Without this check, user could download an invoice for a pending order
    # that hasn't been fulfilled yet — which makes no sense.

    items       = order.items.all()
    status_logs = order.status_logs.all()

    # Render the invoice HTML template.
    
    


    html_string = render_to_string('orders/invoice.html', {
        'order': order,
        'items': items,
        'status_logs': status_logs,
    })

    from weasyprint import HTML
    pdf = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    ).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice-{order.order_number}.pdf"'
    
    return response