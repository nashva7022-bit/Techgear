from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Category, Product, ProductVariant
from .forms import CategoryForm



# CATEGORY VIEWS


@staff_member_required(login_url='admin_login')
@never_cache
def category_list(request):
    # Get all categories ordered by newest first
    categories = Category.objects.all().order_by('-created_at')

    # Search — if admin types in search box
    search = request.GET.get('search', '').strip()
    if search:
        # Filter categories where name contains the search word
        categories = categories.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(id__icontains=search)
        )

    # Pagination — show 8 categories per page
    paginator = Paginator(categories, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats for the top cards
    total = Category.objects.count()
    active = Category.objects.filter(is_active=True).count()
    inactive = Category.objects.filter(is_active=False).count()

    context = {
        'page_obj': page_obj,
        'search': search,
        'total': total,
        'active': active,
        'inactive': inactive,
    }

    return render(request, 'admin_panel/category_management.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully.')
            return redirect('admin_category_list')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = CategoryForm()

    return render(request, 'admin_panel/category_add.html', {'form': form})


@staff_member_required(login_url='admin_login')
@never_cache
def category_edit(request, pk):
    # Get the category or show 404 if not found
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        # Pass instance=category to UPDATE existing, not create new
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('admin_category_list')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'admin_panel/category_edit.html', {
        'form': form,
        'category': category
    })


@staff_member_required(login_url='admin_login')
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    # Soft delete — just set is_active to False
    # Does NOT delete from database
    category.is_active = False
    category.save()
    messages.success(request, f'"{category.name}" has been removed.')
    return redirect('admin_category_list')


@staff_member_required(login_url='admin_login')
@never_cache
def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    # Get all active products in this category
    products = category.products.filter(is_active=True)
    return render(request, 'admin_panel/category_detail.html', {
        'category': category,
        'products': products,
    })



# PRODUCT VIEWS 


@staff_member_required(login_url='admin_login')
@never_cache
def product_list(request):
    return render(request, 'admin_panel/product_management.html')


@staff_member_required(login_url='admin_login')
@never_cache
def product_add(request):
    return render(request, 'admin_panel/product_add.html')


@staff_member_required(login_url='admin_login')
@never_cache
def product_edit(request, pk):
    return render(request, 'admin_panel/product_edit.html')


@staff_member_required(login_url='admin_login')
@require_POST
def product_delete(request, pk):
    return redirect('admin_product_list')



# VARIANT VIEWS — placeholder for now


@staff_member_required(login_url='admin_login')
@never_cache
def variant_list(request):
    return render(request, 'admin_panel/variant_management.html')