from django.shortcuts import render
from django.conf import settings

from weasyprint import HTML
from django.shortcuts import render, redirect, get_object_or_404


from django.contrib.auth.decorators import login_required

from store.models import Review

from django.views.decorators.http import require_POST


from django.views.decorators.cache import never_cache


from django.contrib import messages

from django.http import JsonResponse


from django.db.models import Q

from django.core.paginator import Paginator


from .models import Order, OrderItem, OrderStatusLog



from django.http import HttpResponse
from django.template.loader import render_to_string
from .services import (
    place_cod_order,
    cancel_order,
    cancel_order_item,
    return_order_item,
)


from store.models import Cart


from users.models import Address


from users.forms import AddressForm



#CHECKOUT VIEW 

@login_required
@never_cache
def checkout(request):
    
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

   
    cart_items = list(
        cart.items.select_related(
            'variant__product__category',
            'variant__device_model',
        ).prefetch_related('variant__images')
    )

    addresses    = request.user.addresses.all().order_by('-is_default', '-created_at')
    address_form = AddressForm()

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
            #fetch
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

# ORDER SUCCESS VIEW

@login_required
@never_cache
def order_success(request, order_number):
#fetch

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    
    context = {
        'order': order,
    }
    return render(request, 'orders/order_success.html', context)


# USER ORDER LIST 

@login_required
@never_cache
def order_list(request):
   

    search  = request.GET.get('search', '').strip()

    orders = Order.objects.filter(
        user = request.user
    ).prefetch_related('items')
   


    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(items__product_name__icontains=search)
        ).distinct()
        
       

    paginator = Paginator(orders, settings.ORDERS_PER_PAGE)
    
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
    

    context = {
        'page_obj': page_obj,
        'search':   search,
    }
    return render(request, 'orders/order_list.html', context)


#USER ORDER DETAIL 

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

    reviewed_product_ids = set(
        #fetch
        Review.objects.filter(user=request.user).values_list('product_id', flat=True)
    )

    context = {
        'order':                order,
        'items':                items,
        'status_logs':          status_logs,
        'reviewed_product_ids': reviewed_product_ids,
    }
    return render(request, 'orders/order_detail.html', context)

#CANCEL ENTIRE ORDER

@login_required
@require_POST
def cancel_order_view(request, order_number):
    
    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
    
    reason = request.POST.get('reason', '').strip()
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
   
    try:
        cancel_order(
            order        = order,
            cancelled_by = request.user,
            reason       = reason,
        )
       

        if is_ajax:
            return JsonResponse({
                'ok':      True,
                'message': 'Order cancelled successfully.',
                'status':  'cancelled',
            })
        messages.success(request, "Your order has been cancelled.")
        return redirect('orders:order_detail', order_number=order_number)

    except ValueError as e:
        
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('orders:order_detail', order_number=order_number)


# CANCEL SINGLE ITEM 

@login_required
@require_POST
def cancel_item_view(request, order_number, item_id):
   

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


# RETURN SINGLE ITEM 

@login_required
@require_POST
def return_item_view(request, order_number, item_id):
    
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

   
    if not reason:
        if is_ajax:
            return JsonResponse(
                {'ok': False, 'error': 'Please provide a reason for the return.'},
                status=400,
            )
        messages.error(request, "Please provide a reason for the return.")
        return redirect('orders:order_detail', order_number=order_number)
    

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


#  PDF INVOICE DOWNLOAD 

@login_required
def download_invoice(request, order_number):
    

    order = get_object_or_404(
        Order,
        order_number = order_number,
        user         = request.user,
    )
   
    if order.status not in ['delivered', 'cancelled']:
        messages.error(request, "Invoice is only available for delivered or cancelled orders.")
        return redirect('orders:order_detail', order_number=order_number)
    

    items       = order.items.all()
    status_logs = order.status_logs.all()


    html_string = render_to_string('orders/invoice.html', {
        'order': order,
        'items': items,
        'status_logs': status_logs,
    })

    
    pdf = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    ).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice-{order.order_number}.pdf"'
    
    return response