from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum 
from django.conf import settings
from .models import SiteSettings

from .forms import AdminLoginForm

from django.contrib.auth.decorators import login_required

from wallet.models import Wallet, WalletTransaction  #
User = get_user_model()


def get_or_create_wallet(user):
    
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet






#  ADMIN LOGIN

@never_cache
def admin_login(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('admin_user_management')

    if request.method == 'POST':
        form = AdminLoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email'].lower().strip()
            password = form.cleaned_data['password']

            user = authenticate(request, username=email, password=password)
#did the pswd match
            if user is not None and user.is_superuser and user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name}!")
                return redirect('admin_user_management')
            else:
                messages.error(request, "Invalid credentials or not authorized.")

    else:
        form = AdminLoginForm()

    return render(request, 'admin_panel/login.html', {'form': form})

#  DASHBOARD VIEW
# Replace your entire admin_dashboard view with this

from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

@never_cache
@staff_member_required(login_url='admin_login')
def admin_dashboard(request):
    from orders.models import Order, OrderItem
    from products.models import Product, Category, BRAND_CHOICES

    today      = timezone.now().date()
    this_month = today.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    #  TOP STAT CARDS 
    total_orders   = Order.objects.count()
    total_revenue  = Order.objects.filter(
        status__in=['pending','shipped','out_for_delivery','delivered']
    ).aggregate(r=Sum('total_amount'))['r'] or Decimal('0.00')

    total_users    = User.objects.filter(is_superuser=False).count()
    pending_orders = Order.objects.filter(status='pending').count()
    delivered_orders = Order.objects.filter(status='delivered').count()




    from products.models import ProductVariant

    low_stock_count = ProductVariant.objects.filter(
        product__is_active=True, is_active=True, stock__gt=0, stock__lte=10
    ).count()

      

    pending_returns_count = OrderItem.objects.filter(item_status='return_requested').count()
    out_of_stock_count = ProductVariant.objects.filter(
        product__is_active=True, is_active=True, stock=0
    ).count()
    # Month revenue
    month_revenue = Order.objects.filter(
        created_at__date__gte=this_month,
        status__in=['pending','shipped','out_for_delivery','delivered']
    ).aggregate(r=Sum('total_amount'))['r'] or Decimal('0.00')

    last_month_revenue = Order.objects.filter(
        created_at__date__gte=last_month,
        created_at__date__lt=this_month,
        status__in=['pending','shipped','out_for_delivery','delivered']
    ).aggregate(r=Sum('total_amount'))['r'] or Decimal('0.00')


    aov = (total_revenue / total_orders) if total_orders > 0 else Decimal('0.00')
    

    wallet_liability = Wallet.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    #New vs Returning Customers
    new_customers_this_month = User.objects.filter(
        is_superuser=False,
        date_joined__date__gte=this_month,
    ).count()

    returning_customers_this_month = Order.objects.filter(
        created_at__date__gte=this_month,
        user__date_joined__date__lt=this_month,
    ).values('user').distinct().count()
    
    #  CHART — Weekly / Monthly / Yearly aggregation
    chart_labels  = []
    chart_orders  = []
    chart_revenue = []

    chart_filter = request.GET.get('chart_filter', 'weekly')
    if chart_filter not in ('weekly', 'monthly', 'yearly'):
        chart_filter = 'weekly'

    if chart_filter == 'weekly':
    # Last 7 days, daily buckets
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            label = day.strftime('%d %b')
            day_orders = Order.objects.filter(created_at__date=day).count()
            day_revenue = Order.objects.filter(
                created_at__date=day,
                status__in=['pending','shipped','out_for_delivery','delivered']
            ).aggregate(r=Sum('total_amount'))['r'] or 0

            chart_labels.append(label)
            chart_orders.append(day_orders)
            chart_revenue.append(float(day_revenue))

    elif chart_filter == 'monthly':
    # Current month, daily buckets
        days_in_month = (
            (this_month.replace(month=this_month.month % 12 + 1, day=1)
            if this_month.month != 12
            else this_month.replace(year=this_month.year + 1, month=1, day=1))
            - timedelta(days=1)
        ).day

        for d in range(1, days_in_month + 1):
            try:
                day = this_month.replace(day=d)
            except ValueError:
                break
            if day > today:
                break
            label = day.strftime('%d %b')
            day_orders = Order.objects.filter(created_at__date=day).count()
            day_revenue = Order.objects.filter(
                created_at__date=day,
                status__in=['pending','shipped','out_for_delivery','delivered']
            ).aggregate(r=Sum('total_amount'))['r'] or 0

            chart_labels.append(label)
            chart_orders.append(day_orders)
            chart_revenue.append(float(day_revenue))

    else:  # yearly
    # Last 12 months, monthly buckets
        for i in range(11, -1, -1):
            month_date = (this_month.replace(day=1) - timedelta(days=1))
            for _ in range(i):
                month_date = (month_date.replace(day=1) - timedelta(days=1))
            month_start = month_date.replace(day=1)
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

            label = month_start.strftime('%b %Y')
            month_orders = Order.objects.filter(
                created_at__date__gte=month_start, created_at__date__lte=month_end
            ).count()
            month_revenue_val = Order.objects.filter(
                created_at__date__gte=month_start, created_at__date__lte=month_end,
                status__in=['pending','shipped','out_for_delivery','delivered']
            ).aggregate(r=Sum('total_amount'))['r'] or 0

            chart_labels.append(label)
            chart_orders.append(month_orders)
            chart_revenue.append(float(month_revenue_val))
    

    #BEST SELLING PRODUCTS (Top 10)
    best_products = (
        OrderItem.objects
        .filter(order__status__in=['pending','shipped','out_for_delivery','delivered'])
        .values('product_name')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('subtotal'),
        )
        .order_by('-total_qty')[:10]
    )

    #BEST SELLING CATEGORIES (Top 10) 
    best_categories = (
        OrderItem.objects
        .filter(
            order__status__in=['pending','shipped','out_for_delivery','delivered'],
            variant__product__category__isnull=False,
        )
        .values('variant__product__category__name')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('subtotal'),
        )
        .order_by('-total_qty')[:10]
    )

    # BEST SELLING BRANDS (Top 10)
    best_brands = (
        OrderItem.objects
        .filter(
            order__status__in=['pending','shipped','out_for_delivery','delivered'],
            variant__product__brand__isnull=False,
        )
        .values('variant__product__brand')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('subtotal'),
        )
        .order_by('-total_qty')[:10]
    )

    # Map brand value to label
    brand_map = dict(BRAND_CHOICES)
    best_brands_display = [
        {
            'brand': brand_map.get(b['variant__product__brand'], b['variant__product__brand']),
            'total_qty': b['total_qty'],
            'total_revenue': b['total_revenue'],
        }
        for b in best_brands
    ]

    # RECENT ORDERS (last 8) 
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]

    #  ORDER STATUS BREAKDOWN 
    status_counts = {
        'pending':          Order.objects.filter(status='pending').count(),
        'shipped':          Order.objects.filter(status='shipped').count(),
        'out_for_delivery': Order.objects.filter(status='out_for_delivery').count(),
        'delivered':        Order.objects.filter(status='delivered').count(),
        'cancelled':        Order.objects.filter(status='cancelled').count(),
    }

    context = {
        'wallet_liability': wallet_liability,
        # Stat cards
        'total_orders':        total_orders,
        'total_revenue':       total_revenue,
        'total_users':         total_users,
        'pending_orders':      pending_orders,
        'delivered_orders':    delivered_orders,
        'month_revenue':       month_revenue,
        'last_month_revenue':  last_month_revenue,
        #out of stock and lowstock
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        #pending return
        'pending_returns_count': pending_returns_count,

        'aov': aov,
        #new returning customers
        'new_customers_this_month': new_customers_this_month,
        'returning_customers_this_month': returning_customers_this_month,

        'chart_filter': chart_filter,

        # Chart data (JSON for JS)
        'chart_labels':   json.dumps(chart_labels),
        'chart_orders':   json.dumps(chart_orders),
        'chart_revenue':  json.dumps(chart_revenue),

        # Best sellers
        'best_products':   best_products,
        'best_categories': best_categories,
        'best_brands':     best_brands_display,

        # Recent orders
        'recent_orders': recent_orders,

        # Status breakdown
        'status_counts': status_counts,

        'today': today,
    }
    return render(request, 'admin_panel/dashboard.html', context)
#  USER MANAGEMENT 

@never_cache
@staff_member_required(login_url='admin_login')
def user_list(request):
    # 1. Base Query
    users_query = User.objects.filter(is_superuser=False).annotate(
        order_count=Count('order')
    )

    # 2. Search
    query = request.GET.get('search', '').strip()
    if query:
        users_query = users_query.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # 3. Sorting
    sort = request.GET.get('sort', '-date_joined')
    if sort not in ['-date_joined', 'date_joined']:
        sort = '-date_joined'
    users_query = users_query.order_by(sort)

    # 4. Pagination
    paginator = Paginator(users_query, 10)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)

    # 5. Stats (Using the base_stats variable to avoid repeating filter logic)
    base_stats = User.objects.filter(is_superuser=False)
    
    context = {
        'users': users,
        'search_query': query,
        'total_users': base_stats.count(),
        'active_users': base_stats.filter(is_verified=True, is_blocked=False).count(),
        'blocked_users': base_stats.filter(is_blocked=True).count(),
        'pending_users': base_stats.filter(is_verified=False).count(),
        'admin_users': User.objects.filter(is_superuser=True).count(),
    }

    # 6. Detail Drawer Logic
    view_user_id = request.GET.get('view_user')
    if view_user_id:
        selected_user = get_object_or_404(User, id=view_user_id)
        context['selected_user'] = selected_user
        context['user_addresses'] = selected_user.addresses.all().order_by('-is_default')

    # 7. AJAX Check for Live Search
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'admin_panel/partials/user_table.html', context)

    # 8. Standard Return (Make sure this is outside the IF and correctly indented)
    return render(request, 'admin_panel/user_management.html', context)
# BLOCK / UNBLOCK USER

@never_cache
@staff_member_required(login_url='admin_login')
@require_POST
def toggle_user_status(request, user_id):

    user = get_object_or_404(User, id=user_id)

    #  Prevent blocking admin
    if user.is_superuser:
        messages.error(request, "You cannot block an administrator.")
        return redirect('admin_user_management')
#It flips the current status to the opposite
    # Toggle block
    user.is_blocked = not user.is_blocked

    if user.is_blocked:
        user.is_active = False
    else:
        user.is_active = user.is_verified  # only verified users become active

    user.save()
    
    status = "blocked" if user.is_blocked else "unblocked"
    messages.success(request, f"{user.email} has been {status}.")

    return redirect('admin_user_management')



# ADMIN LOGOUT

@require_POST
def admin_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('admin_login')

@staff_member_required(login_url='admin_login')
@never_cache
def site_settings(request):
   
    settings_obj = SiteSettings.get()

    if request.method == 'POST':
        fee = request.POST.get('customization_fee', '').strip()
        try:
            fee = float(fee)
            if fee < 0:
                raise ValueError()
            settings_obj.customization_fee = fee
            settings_obj.save()
            messages.success(request, 'Settings saved successfully.')
            return redirect('admin_site_settings')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid fee amount (0 or more).')

    return render(request, 'admin_panel/site_settings.html', {
        'settings': settings_obj,
    })


    # ADMIN WALLET VIEW 

@staff_member_required(login_url='admin_login')
@never_cache
def admin_wallet_list(request):
    
    from django.db.models import Q
    search = request.GET.get('search', '').strip()

    wallets = Wallet.objects.select_related('user').order_by('-balance')

    if search:
        wallets = wallets.filter(
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    paginator   = Paginator(wallets, 20)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search':   search,
    }
    return render(request, 'admin_panel/wallet_list.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def admin_wallet_detail(request, user_id):
    """
    Admin page — shows one user's wallet and full transaction history.
    """
    from django.contrib.auth import get_user_model
    User   = get_user_model()
    user   = get_object_or_404(User, pk=user_id)
    wallet = get_or_create_wallet(user)

    transactions = wallet.transactions.select_related('order').all()
    paginator    = Paginator(transactions, 15)
    page_obj     = paginator.get_page(request.GET.get('page'))

    context = {
        'wallet_user': user,
        'wallet':      wallet,
        'page_obj':    page_obj,
    }
    return render(request, 'admin_panel/wallet_detail.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def admin_wallet_credit(request, user_id):
    """
    Admin manually credits a user's wallet.
    Used for compensation, promotional credits, referral rewards etc.
    """
    User   = get_user_model()
    user   = get_object_or_404(User, pk=user_id)
    wallet = get_or_create_wallet(user)

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '').strip()
        reason     = request.POST.get('reason', '').strip()

        try:
            from decimal import Decimal
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid amount greater than 0.')
            return redirect('admin_wallet_detail', user_id=user_id)

        if not reason:
            messages.error(request, 'A reason is required.')
            return redirect('admin_wallet_detail', user_id=user_id)

        wallet.credit(amount=amount, reason=reason, order=None)
        messages.success(request, f'₹{amount} credited to {user.email}\'s wallet.')
        return redirect('admin_wallet_detail', user_id=user_id)

    return render(request, 'admin_panel/wallet_credit.html', {
        'wallet_user': user,
        'wallet':      wallet,
    })