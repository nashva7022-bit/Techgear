from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
import json
 
from .forms import CategoryForm, ProductForm, ProductVariantForm, ProductSpecificationForm
from .models import Category, Product, ProductVariant, VariantImage, ProductSpecification

# CATEGORY VIEWS


@staff_member_required(login_url='admin_login')
@never_cache
def category_list(request):

    # Search
    search = request.GET.get('search', '').strip()
    # Sort
    sort_by = request.GET.get('sort', 'newest')  # default: newest first

    # Sort mapping
    sort_options = {
        'newest':    '-created_at',
        'oldest':    'created_at',
        'name_asc':  'name',
        'name_desc': '-name',
    }
    order_field = sort_options.get(sort_by, '-created_at')

    # Base queryset
    categories = Category.objects.all().order_by(order_field)

    # Apply search filter
    if search:
        categories = categories.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(id__icontains=search)
        )

    # Pagination — 8 per page
    paginator = Paginator(categories, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total    = Category.objects.count()
    active   = Category.objects.filter(is_active=True).count()
    inactive = Category.objects.filter(is_active=False).count()

    context = {
        'page_obj': page_obj,
        'search':   search,
        'sort_by':  sort_by,
        'total':    total,
        'active':   active,
        'inactive': inactive,
    }

    return render(request, 'admin_panel/category_management.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, )
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
        form = CategoryForm(request.POST, instance=category)
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
    if category.is_active:
        category.is_active = False
        category.save()
        category.products.update(is_active=False)
        messages.success(request, f'"{category.name}" and its products have been deactivated.')
    else:
        category.is_active = True
        category.save()
        category.products.update(is_active=True)
        messages.success(request, f'"{category.name}" and its products have been activated.')
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
    search      = request.GET.get('search', '').strip()
    sort_by     = request.GET.get('sort', 'newest')
    category_id = request.GET.get('category', '').strip()
    brand       = request.GET.get('brand', '').strip()

    sort_options = {
        'newest':    '-created_at',
        'oldest':    'created_at',
        'name_asc':  'name',
        'name_desc': '-name',
    }
    order_field = sort_options.get(sort_by, '-created_at')

    products = Product.objects.select_related('category').prefetch_related(
        'variants__images'
    ).order_by(order_field)

    # Filter by category
    if category_id:
        products = products.filter(category__id=category_id)

    # Filter by brand
    if brand:
        products = products.filter(brand=brand)

    # Filter by search
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(category__name__icontains=search)
        )

    paginator   = Paginator(products, 6)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    total    = Product.objects.count()
    active   = Product.objects.filter(is_active=True).count()
    inactive = Product.objects.filter(is_active=False).count()

    context = {
        'page_obj':    page_obj,
        'search':      search,
        'sort_by':     sort_by,
        'category_id': category_id,
        'brand':       brand,
        'total':       total,
        'active':      active,
        'inactive':    inactive,
        # For dropdowns
        'categories':  Category.objects.filter(is_active=True).order_by('name'),
        'brand_choices': Product._meta.get_field('brand').choices,
    }
    return render(request, 'admin_panel/product_management.html', context)

@staff_member_required(login_url='admin_login')
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.is_active:
        product.is_active = False
        messages.success(request, f'"{product.name}" has been deactivated.')
    else:
        product.is_active = True
        messages.success(request, f'"{product.name}" has been activated.')
    product.save()
    return redirect('admin_product_list')


@staff_member_required(login_url='admin_login')
@require_POST
def product_toggle_customization(request, pk):
    
    product = get_object_or_404(Product, pk=pk)
    product.is_customizable = not product.is_customizable
    product.save()
    return JsonResponse({'is_customizable': product.is_customizable})

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
MAX_IMAGE_SIZE      = 5 * 1024 * 1024  # 5 MB
 
 
def _validate_image(img):
    """Returns error string or None."""
    if img.content_type not in ALLOWED_IMAGE_TYPES:
        return f'"{img.name}" is not a valid image type (JPEG, PNG, WebP only).'
    if img.size > MAX_IMAGE_SIZE:
        return f'"{img.name}" exceeds the 5 MB size limit.'
    return None
 
 
def _save_specs(product, post_data):
    """
    Reads spec_name[] and spec_value[] from POST and saves them.
    Deletes existing specs first (full replace on edit).
    """
    product.specifications.all().delete()
    names  = post_data.getlist('spec_name')
    values = post_data.getlist('spec_value')
    specs  = []
    for i, (name, value) in enumerate(zip(names, values)):
        name  = name.strip()
        value = value.strip()
        if name and value:
            specs.append(ProductSpecification(
                product=product, name=name, value=value, order=i
            ))
    if specs:
        ProductSpecification.objects.bulk_create(specs)
 
 
def _save_variants(product, post_data, files):
    """
    Reads variant fields from POST (variant_device_model[], etc.)
    and saves each variant + its images.
    Returns a list of error strings (empty = all good).
    """
    errors = []
 
    device_models = post_data.getlist('variant_device_model')
    case_types    = post_data.getlist('variant_case_type')
    colors        = post_data.getlist('variant_color')
    color_codes   = post_data.getlist('variant_color_code')
    skus          = post_data.getlist('variant_sku')
    prices        = post_data.getlist('variant_price')
    stocks        = post_data.getlist('variant_stock')
 
    if not device_models:
        errors.append('At least one variant is required.')
        return errors
 
    for i, device_model in enumerate(device_models):
        device_model = device_model.strip()
        if not device_model:
            errors.append(f'Variant {i + 1}: Device model is required.')
            continue
 
        # Collect images for this variant index
        image_key  = f'variant_images_{i}'
        images     = files.getlist(image_key)
 
        if len(images) < 3:
            errors.append(f'Variant {i + 1}: Please upload at least 3 images.')
            continue
 
        # Validate images
        img_error = False
        for img in images:
            err = _validate_image(img)
            if err:
                errors.append(f'Variant {i + 1}: {err}')
                img_error = True
        if img_error:
            continue
 
        # Build + save variant
        sku = skus[i].strip() if i < len(skus) else ''
 
        try:
            price = float(prices[i]) if i < len(prices) else 0
            stock = int(stocks[i])   if i < len(stocks) else 0
        except (ValueError, TypeError):
            errors.append(f'Variant {i + 1}: Invalid price or stock value.')
            continue
 
        variant = ProductVariant(
            product      = product,
            device_model = device_model,
            case_type    = case_types[i].strip() if i < len(case_types) else '',
            color        = colors[i]             if i < len(colors)     else 'other',
            color_code   = color_codes[i].strip() if i < len(color_codes) else '#000000',
            sku = sku or '' , # auto-generated in model.save() if blank
            price        = price,
            stock        = stock,
        )
        variant.save()
 
        # Save images
        for j, img in enumerate(images):
            VariantImage.objects.create(
                variant    = variant,
                image      = img,
                is_primary = (j == 0),
                order      = j,
            )
 
    return errors
 
@staff_member_required(login_url='admin_login')
@never_cache
def product_add(request):
    form = ProductForm()
 
    if request.method == 'POST':
        form = ProductForm(request.POST)
 
        if form.is_valid():
            product = form.save()
 
            # Save specifications
            _save_specs(product, request.POST)
 
            # Save variants
            variant_errors = _save_variants(product, request.POST, request.FILES)
            if variant_errors:
                # Roll back product if variants failed
                product.delete()
                for err in variant_errors:
                    messages.error(request, err)
                return render(request, 'admin_panel/product_add.html', {
                    'form':       form,
                    'categories': Category.objects.filter(is_active=True),
                })
 
            messages.success(request, f'"{product.name}" added successfully.')
            return redirect('admin_product_list')
        else:
            messages.error(request, 'Please fix the errors below.')
 
    return render(request, 'admin_panel/product_add.html', {
        'form':       form,
        'categories': Category.objects.filter(is_active=True),
    })
 
 
# ──────────────────────────────────────────
# PRODUCT EDIT
# ──────────────────────────────────────────
 
@staff_member_required(login_url='admin_login')
@never_cache
def product_edit(request, pk):
    product          = get_object_or_404(Product, pk=pk)
    existing_variants = product.variants.prefetch_related('images').all()
 
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
 
        if form.is_valid():
            product = form.save()
 
            # Replace specifications
            _save_specs(product, request.POST)
 
            # Handle existing variant updates
            _handle_existing_variants(request.POST, request.FILES, existing_variants)
 
            # Add brand-new variants
            new_errors = _save_new_variants(product, request.POST, request.FILES)
            if new_errors:
                for err in new_errors:
                    messages.error(request, err)
 
            messages.success(request, f'"{product.name}" updated successfully.')
            return redirect('admin_product_list')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductForm(instance=product)
 
    return render(request, 'admin_panel/product_edit.html', {
        'form':              form,
        'product':           product,
        'existing_variants': existing_variants,
        'specifications':    product.specifications.all(),
        'categories':        Category.objects.filter(is_active=True),
    })
 
 
def _handle_existing_variants(post_data,request, files, existing_variants):
    """Update price/stock/color etc. for variants that already exist."""
    for variant in existing_variants:
        prefix = f'existing_variant_{variant.pk}'
 
        price_val = post_data.get(f'{prefix}_price')
        stock_val = post_data.get(f'{prefix}_stock')
        color     = post_data.get(f'{prefix}_color',      variant.color)
        color_code = post_data.get(f'{prefix}_color_code', variant.color_code)
        case_type  = post_data.get(f'{prefix}_case_type',  variant.case_type)
        is_active = f'{prefix}_is_active' in post_data
 
        try:
            if price_val:
                variant.price = float(price_val)
            if stock_val:
                variant.stock = int(stock_val)
            variant.color      = color
            variant.color_code = color_code
            variant.case_type  = case_type
            variant.is_active  = is_active
            variant.save()
        except (ValueError, TypeError):
            pass

       
        # Delete selected images
        delete_ids = post_data.getlist(f'{prefix}_delete_images')
        
        # New images
        new_imgs = files.getlist(f'{prefix}_images')
        
        # Calculate resulting count
        current_count = variant.images.count()
        total_after_change = (current_count - len(delete_ids)) + len(new_imgs)
        
        if total_after_change < 3:
            
            messages.error(request, f'Variant {variant.device_model}: You must keep at least 3 images.')
            continue 
            
        # If valid, proceed with delete and create
        if delete_ids:
            variant.images.filter(pk__in=delete_ids).delete()
            
        for img in new_imgs:
            err = _validate_image(img)
            if not err:
                VariantImage.objects.create(
                    variant=variant,
                    image=img,
                    is_primary=False,
                    order=variant.images.count() + 1,
                )
        
 
 
def _save_new_variants(product, post_data, files):
    errors = []

    device_models = post_data.getlist('new_variant_device_model')  # ← was missing!
    if not device_models:
        return errors

    case_types  = post_data.getlist('new_variant_case_type')
    colors      = post_data.getlist('new_variant_color')
    color_codes = post_data.getlist('new_variant_color_code')
    skus        = post_data.getlist('new_variant_sku')
    prices      = post_data.getlist('new_variant_price')
    stocks      = post_data.getlist('new_variant_stock')

    for i, device_model in enumerate(device_models):
        device_model = device_model.strip()
        if not device_model:
            errors.append(f'New variant {i + 1}: Device model is required.')  # ← fixed
            continue

        images = files.getlist(f'new_variant_images_{i}')
        if len(images) < 3:
            errors.append(f'New variant {i + 1}: Please upload at least 3 images.')
            continue

        img_error = False
        for img in images:
            err = _validate_image(img)
            if err:
                errors.append(f'New variant {i + 1}: {err}')
                img_error = True
        if img_error:
            continue

        sku = skus[i].strip() if i < len(skus) else ''
        try:
            price = float(prices[i]) if i < len(prices) else 0
            stock = int(stocks[i])   if i < len(stocks) else 0
        except (ValueError, TypeError):
            errors.append(f'New variant {i + 1}: Invalid price or stock.')
            continue

        variant = ProductVariant(
            product      = product,
            device_model = device_model,
            case_type    = case_types[i].strip() if i < len(case_types) else '',
            color        = colors[i]             if i < len(colors)     else 'other',
            color_code   = color_codes[i].strip() if i < len(color_codes) else '#000000',
            sku          = sku or '',
            price        = price,
            stock        = stock,
        )
        variant.save()

        for j, img in enumerate(images):
            VariantImage.objects.create(
                variant    = variant,
                image      = img,
                is_primary = (j == 0),
                order      = j,
            )

    return errors
 
# ══════════════════════════════════════════
# VARIANT AJAX VIEWS
# ══════════════════════════════════════════
 
@staff_member_required(login_url='admin_login')
@require_POST
def variant_delete(request, pk):
    """Soft-delete a variant."""
    variant = get_object_or_404(ProductVariant, pk=pk)
    if variant.is_active:
        variant.is_active = False
        variant.save()
        msg = 'Variant deactivated.'
    else:
        variant.is_active = True
        variant.save()
        msg = 'Variant activated.'
    return JsonResponse({'success': True, 'message': msg, 'is_active': variant.is_active})
 
 
@staff_member_required(login_url='admin_login')
@never_cache
def variant_list(request):
    return render(request, 'admin_panel/variant_management.html')