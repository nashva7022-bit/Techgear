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
    """
    Gets the user's wallet, creating one with ₹0 balance if it doesn't exist.
    Use this everywhere instead of Wallet.objects.get() or .first()
    """
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
@never_cache
@staff_member_required(login_url='admin_login')
def admin_dashboard(request):
    # Stats for the top cards
    
    
    context = {
        'total_orders': User.objects.annotate(c=Count('order')).aggregate(Sum('c'))['c__sum'] or 0,
        'total_revenue': 48392, # Placeholder until you have an Order 'total' field
        'total_users': User.objects.filter(is_superuser=False).count(),
        'pending_orders': 87,   # Placeholder
        
        
        # 'recent_orders': Order.objects.all().order_by('-created_at')[:5]
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
    """
    Admin page to configure site-wide settings.
    Currently: customization fee.
    Add more fields to SiteSettings model as needed.
    """
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


    # ── ADMIN WALLET VIEW ─────────────────────────────────────────────────────────

@staff_member_required(login_url='admin_login')
@never_cache
def admin_wallet_list(request):
    """
    Admin page — shows all user wallets with their balances.
    Useful for support — admin can see any user's wallet.
    """
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