from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.conf import settings
from orders.services import approve_return, reject_return

from orders.models import Order, OrderItem, OrderStatusLog, VALID_TRANSITIONS
from orders.services import change_order_status
from products.models import ProductVariant, Category
from admin_orders.models import ActivityLog, log_activity
from orders.services import cancel_order_item

from datetime import datetime

# ADMIN ORDER LIST


@staff_member_required(login_url='admin_login')
@never_cache
def order_list(request):
    search     = request.GET.get('search', '').strip()
    status     = request.GET.get('status', '').strip()
    sort_by    = request.GET.get('sort', 'newest')
    date_from  = request.GET.get('date_from', '').strip()
    date_to    = request.GET.get('date_to', '').strip()

    orders = Order.objects.select_related('user').prefetch_related('items')#reverse

    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(items__product_name__icontains=search) |
            Q(shipping_full_name__icontains=search)
        ).distinct()

    if status:
        orders = orders.filter(status=status)

    if date_from:
        try:
            
            orders = orders.filter(
                created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    if date_to:
        try:
            
            orders = orders.filter(
                created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date()
            )
        except ValueError:
            pass

    sort_options = {
        'newest':      '-created_at',
        'oldest':      'created_at',
        'amount_high': '-total_amount',
        'amount_low':  'total_amount',
    }
    orders = orders.order_by(sort_options.get(sort_by, '-created_at'))

    status_counts = {
        'all':              Order.objects.count(),
        'pending':          Order.objects.filter(status='pending').count(),
        'shipped':          Order.objects.filter(status='shipped').count(),
        'out_for_delivery': Order.objects.filter(status='out_for_delivery').count(),
        'delivered':        Order.objects.filter(status='delivered').count(),
        'cancelled':        Order.objects.filter(status='cancelled').count(),
    }

  
    paginator = Paginator(orders, settings.ORDERS_PER_PAGE)#splits
    page_number = request.GET.get('page')#current
    page_obj    = paginator.get_page(page_number)#orders belonging to that page

    context = {
        'page_obj':      page_obj,
        'search':        search,
        'status':        status,
        'sort_by':       sort_by,
        'date_from':     date_from,
        'date_to':       date_to,
        'status_counts': status_counts,
        'has_filters':   any([search, status, date_from, date_to]),
    }
    return render(request, 'admin_orders/order_list.html', context)


# ADMIN ORDER DETAIL


@staff_member_required(login_url='admin_login')
@never_cache
def order_detail(request, order_number):
    order       = get_object_or_404(Order, order_number=order_number)
    items       = order.items.select_related('variant').prefetch_related('variant__images')
    status_logs = order.status_logs.select_related('changed_by').all()#to get the admin
    allowed_next = VALID_TRANSITIONS.get(order.status, [])

    status_labels = dict([
        ('pending',          'Pending'),
        ('shipped',          'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered',        'Delivered'),
        ('cancelled',        'Cancelled'),
    ])

    next_statuses = [
        #dropdown
        {'value': s, 'label': status_labels.get(s, s)}
        for s in allowed_next
    ]

    context = {
        'order':         order,
        'items':         items,
        'status_logs':   status_logs,
        'next_statuses': next_statuses,
        'allowed_next':  allowed_next,
    }
    return render(request, 'admin_orders/order_detail.html', context)



# ADMIN CHANGE ORDER STATUS


@staff_member_required(login_url='admin_login')
@require_POST
def change_status(request, order_number):
    order      = get_object_or_404(Order, order_number=order_number)
    new_status = request.POST.get('new_status', '').strip()
    note       = request.POST.get('note', '').strip()
    
    is_ajax    = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not new_status:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'No status provided.'}, status=400)
        messages.error(request, 'Please select a status.')
        return redirect('admin_orders:order_detail', order_number=order_number)

    try:
        change_order_status(
            order      = order,
            new_status = new_status,
            changed_by = request.user,
            note       = note,
        )

        
        log_activity(
            admin        = request.user,
            action       = 'order_status_change',
            description  = f'Order {order.order_number} status changed to {new_status}.',
            order_number = order.order_number,
        )

        if is_ajax:
            return JsonResponse({
                'ok':         True,
                'message':    f'Order status updated to {order.get_status_display()}.',
                'new_status': new_status,
                'new_label':  order.get_status_display(),
            })
        messages.success(request, f'Order {order.order_number} status updated to {order.get_status_display()}.')
        return redirect('admin_orders:order_detail', order_number=order_number)

    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('admin_orders:order_detail', order_number=order_number)



# ADMIN INVENTORY
@staff_member_required(login_url='admin_login')
@never_cache
def inventory_list(request):
    search       = request.GET.get('search', '').strip()
    category_id  = request.GET.get('category', '').strip()
    stock_filter = request.GET.get('stock', '').strip()
    sort_by      = request.GET.get('sort', 'low_stock')

    variants = ProductVariant.objects.select_related(
        'product__category',
        'device_model',
    ).filter(
        product__is_active=True,
        is_active=True,
    )

    if search:
        variants = variants.filter(
            Q(product__name__icontains=search) |
            Q(sku__icontains=search) |
            Q(device_model__name__icontains=search)
        )

    if category_id:
        variants = variants.filter(product__category__id=category_id)

    if stock_filter == 'out_of_stock':
        variants = variants.filter(stock=0)
    elif stock_filter == 'low_stock':
        variants = variants.filter(stock__gt=0, stock__lte=10)
    elif stock_filter == 'in_stock':
        variants = variants.filter(stock__gt=10)

    sort_options = {
        'low_stock':  'stock',
        'high_stock': '-stock',
        'name_asc':   'product__name',
        'name_desc':  '-product__name',
    }
    variants = variants.order_by(sort_options.get(sort_by, 'stock'))

    all_variants    = ProductVariant.objects.filter(product__is_active=True, is_active=True)
    out_of_stock    = all_variants.filter(stock=0).count()
    low_stock_count = all_variants.filter(stock__gt=0, stock__lte=10).count()
    in_stock_count  = all_variants.filter(stock__gt=10).count()

    paginator   = Paginator(variants, 20)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'page_obj':        page_obj,
        'search':          search,
        'category_id':     category_id,
        'stock_filter':    stock_filter,
        'sort_by':         sort_by,
        'categories':      Category.objects.filter(is_active=True).order_by('name'),
        'out_of_stock':    out_of_stock,
        'low_stock_count': low_stock_count,
        'in_stock_count':  in_stock_count,
        'total_variants':  all_variants.count(),
        'has_filters':     any([search, category_id, stock_filter]),
    }
    return render(request, 'admin_orders/inventory_list.html', context)



# ADMIN UPDATE STOCk


@staff_member_required(login_url='admin_login')
@require_POST
def update_stock(request, variant_id):
    variant   = get_object_or_404(ProductVariant, pk=variant_id)
    new_stock = request.POST.get('stock', '').strip()
    is_ajax   = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        new_stock = int(new_stock)
        if new_stock < 0:
            raise ValueError("Stock cannot be negative.")
    except (ValueError, TypeError):
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Invalid stock value.'}, status=400)
        messages.error(request, 'Invalid stock value.')
        return redirect('admin_orders:inventory_list')

    old_stock     = variant.stock
    variant.stock = new_stock
    variant.save(update_fields=['stock'])

   
    log_activity(
        admin       = request.user,
        action      = 'stock_update',
        description = f'Stock for "{variant}" updated from {old_stock} to {new_stock}.',
        variant_id  = variant.pk,
    )

    if is_ajax:
        return JsonResponse({
            'ok':       True,
            'message':  f'Stock updated from {old_stock} to {new_stock}.',
            'new_stock': new_stock,
            'status':   'out_of_stock' if new_stock == 0 else ('low' if new_stock <= 10 else 'ok'),
        })

    messages.success(request, f'Stock for "{variant}" updated to {new_stock}.')
    return redirect('admin_orders:inventory_list')


# ADMIN ACTIVITY LOG


@staff_member_required(login_url='admin_login')
@never_cache
def activity_log(request):
   
    logs = ActivityLog.objects.select_related('admin').all()
   
    paginator   = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {'page_obj': page_obj}
    return render(request, 'admin_orders/activity_log.html', context)




@staff_member_required(login_url='admin_login')
@never_cache
def return_requests(request):
    search  = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    items = OrderItem.objects.filter(
        item_status='return_requested'
    ).select_related('order__user', 'variant__product').prefetch_related('variant__images')

    if search:
        items = items.filter(
            Q(order__order_number__icontains=search) |
            Q(product_name__icontains=search)        |
            Q(order__user__email__icontains=search)
        )

    items = items.order_by(
        'order__created_at' if sort_by == 'oldest' else '-order__created_at'
    )

    paginator = Paginator(items, 15)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':       page_obj,
        'search':         search,
        'sort_by':        sort_by,
        'total_pending':  OrderItem.objects.filter(item_status='return_requested').count(),
        'total_approved': OrderItem.objects.filter(item_status='returned').count(),
        
        'total_rejected': OrderItem.objects.filter(
            item_status='return_rejected'
        ).count(),
    }
    return render(request, 'admin_orders/return_requests.html', context)

#approve return
@staff_member_required(login_url='admin_login')
@require_POST
def approve_return_view(request, order_number, item_id):
    order = get_object_or_404(Order, order_number=order_number)
    item  = get_object_or_404(OrderItem, pk=item_id, order=order)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        approve_return(order_item=item, approved_by=request.user)
        if is_ajax:
            return JsonResponse({'ok': True, 'message': f'Return approved for "{item.product_name}".'})
        messages.success(request, f'Return approved for "{item.product_name}". Stock restored.')
        return redirect('admin_orders:order_detail', order_number=order_number)
    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('admin_orders:order_detail', order_number=order_number)

#rejuct return

@staff_member_required(login_url='admin_login')
@require_POST
def reject_return_view(request, order_number, item_id):
    order  = get_object_or_404(Order, order_number=order_number)
    item   = get_object_or_404(OrderItem, pk=item_id, order=order)
    reason = request.POST.get('reason', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        reject_return(order_item=item, rejected_by=request.user, reason=reason)
        if is_ajax:
            return JsonResponse({'ok': True, 'message': f'Return rejected for "{item.product_name}".'})
        messages.success(request, f'Return rejected for "{item.product_name}".')
        return redirect('admin_orders:order_detail', order_number=order_number)
    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('admin_orders:order_detail', order_number=order_number)
    
#cancel single item

@staff_member_required(login_url='admin_login')
@require_POST
def admin_cancel_item(request, order_number, item_id):
    order   = get_object_or_404(Order, order_number=order_number)
    item    = get_object_or_404(OrderItem, pk=item_id, order=order)
    reason  = request.POST.get('reason', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        cancel_order_item(
            order_item   = item,
            cancelled_by = request.user,
            reason       = reason,
        )
        if is_ajax:
            return JsonResponse({'ok': True, 'message': f'"{item.product_name}" cancelled.'})
        messages.success(request, f'"{item.product_name}" cancelled.')
        return redirect('admin_orders:order_detail', order_number=order_number)
    except ValueError as e:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))
        return redirect('admin_orders:order_detail', order_number=order_number)