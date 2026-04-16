from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum 

from .forms import AdminLoginForm

User = get_user_model()



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
   
    # Base Query (exclude admins)
    users_query = User.objects.filter(is_superuser=False)

    # Add Order Count (IMPORTANT for Figma)
    users_query = users_query.annotate(
        order_count=Count('order')  # make sure Order model exists
    )

    # Search (email, first name, last name)
    query = request.GET.get('search', '').strip()
    if query:
        users_query = users_query.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Sorting (LATEST FIRST — REQUIRED)
    sort = request.GET.get('sort', '-date_joined')

    # Safety check 
    if sort not in ['-date_joined', 'date_joined']:
        sort = '-date_joined'

    users_query = users_query.order_by(sort)

    

    # Pagination
    paginator = Paginator(users_query, 3)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)

    # Stats logic
    total_users = User.objects.filter(is_superuser=False).count()
    active_users = User.objects.filter(is_superuser=False, is_blocked=False).count()
    blocked_users = User.objects.filter(is_superuser=False, is_blocked=True).count()
    admin_users = User.objects.filter(is_superuser=True).count()
   

   
    view_user_id = request.GET.get('view_user')
    selected_user = None
    user_addresses = None

    if view_user_id:
        selected_user = get_object_or_404(User, id=view_user_id)
        # Pulls addresses using the related_name='addresses' from your Address model
        user_addresses = selected_user.addresses.all().order_by('-is_default')

 #sending in to the html file
    context = {
        'users': users,
        'search_query': query,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'admin_users': admin_users,
        'selected_user': selected_user,
        'user_addresses': user_addresses,
    }

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
    user.is_active = not user.is_blocked
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