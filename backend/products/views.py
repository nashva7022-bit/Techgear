from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

from .forms import CategoryForm, ProductForm, ProductVariantForm, ProductSpecificationForm
from .models import Category, Product, ProductVariant, VariantImage, ProductSpecification


# ══════════════════════════════════════════
# CATEGORY VIEWS
# ══════════════════════════════════════════

@staff_member_required(login_url='admin_login')
@never_cache
def category_list(request):
    search   = request.GET.get('search', '').strip()
    sort_by  = request.GET.get('sort', 'newest')

    sort_options = {
        'newest':    '-created_at',
        'oldest':    'created_at',
        'name_asc':  'name',
        'name_desc': '-name',
    }
    order_field = sort_options.get(sort_by, '-created_at')

    categories = Category.objects.all().order_by(order_field)

    if search:
        categories = categories.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(id__icontains=search)
        )

    paginator   = Paginator(categories, 4)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

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
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
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
        'category': category,
    })


@staff_member_required(login_url='admin_login')
@require_POST
def category_toggle_status(request, pk):
    """Soft activate/deactivate a category and cascade to its products."""
    category = get_object_or_404(Category, pk=pk)
    if category.is_active:
        category.is_active = False
        category.save()
        # Only cascade-deactivate products that are currently active.
        # Flag them so we know exactly which ones to restore later.
        category.products.filter(is_active=True).update(
            is_active=False,
            deactivated_by_category=True,
        )
        messages.success(
            request,
            f'"{category.name}" and its products have been deactivated.'
        )
    else:
        category.is_active = True
        category.save()
        # Only restore products that were deactivated by this cascade —
        # not ones the admin manually deactivated before the category was deactivated.
        category.products.filter(deactivated_by_category=True).update(
            is_active=True,
            deactivated_by_category=False,
        )
        messages.success(
            request,
            f'"{category.name}" and its products have been activated.'
        )
    return redirect('admin_category_list')


@staff_member_required(login_url='admin_login')
@never_cache
def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    products = category.products.filter(is_active=True)
    return render(request, 'admin_panel/category_detail.html', {
        'category': category,
        'products': products,
    })


# ══════════════════════════════════════════
# PRODUCT VIEWS
# ══════════════════════════════════════════

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

    if category_id:
        products = products.filter(category__id=category_id)
    if brand:
        products = products.filter(brand=brand)
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
        'page_obj':      page_obj,
        'search':        search,
        'sort_by':       sort_by,
        'category_id':   category_id,
        'brand':         brand,
        'total':         total,
        'active':        active,
        'inactive':      inactive,
        'categories':    Category.objects.filter(is_active=True).order_by('name'),
        'brand_choices': Product._meta.get_field('brand').choices,
    }
    return render(request, 'admin_panel/product_management.html', context)


@staff_member_required(login_url='admin_login')
@require_POST
def product_toggle_status(request, pk):
    """Soft activate/deactivate a product."""
    product = get_object_or_404(Product, pk=pk)
    if product.is_active:
        product.is_active = False
        messages.success(request, f'"{product.name}" has been deactivated.')
    else:
        product.is_active = True
        messages.success(request, f'"{product.name}" has been activated.')
    product.save()
    return redirect('admin_product_list')


# ──────────────────────────────────────────
# Image / variant helpers
# ──────────────────────────────────────────

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
MAX_IMAGE_SIZE      = 5 * 1024 * 1024  # 5 MB


def _validate_image(img):
    """Returns an error string or None."""
    if img.content_type not in ALLOWED_IMAGE_TYPES:
        return f'"{img.name}" is not a valid image type (JPEG, PNG, WebP only).'
    if img.size > MAX_IMAGE_SIZE:
        return f'"{img.name}" exceeds the 5 MB size limit.'
    return None


def _save_specs(product, post_data):
    """Full-replace specifications from POST data."""
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
    Reads new variant fields from POST and saves each variant + images.
    Returns a list of error strings (empty list = success).
    """
    errors = []

    device_models = post_data.getlist('variant_device_model')
    if not device_models:
        errors.append('At least one variant is required.')
        return errors

    case_types  = post_data.getlist('variant_case_type')
    colors      = post_data.getlist('variant_color')
    color_codes = post_data.getlist('variant_color_code')
    skus        = post_data.getlist('variant_sku')
    prices      = post_data.getlist('variant_price')
    stocks      = post_data.getlist('variant_stock')

    for i, device_model in enumerate(device_models):
        device_model = device_model.strip()
        if not device_model:
            errors.append(f'Variant {i + 1}: Device model is required.')
            continue

        images = files.getlist(f'variant_images_{i}')
        if len(images) < 3:
            errors.append(f'Variant {i + 1}: Please upload at least 3 images.')
            continue

        img_error = False
        for img in images:
            err = _validate_image(img)
            if err:
                errors.append(f'Variant {i + 1}: {err}')
                img_error = True
        if img_error:
            continue

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
            case_type    = case_types[i].strip()  if i < len(case_types)  else '',
            color        = colors[i]              if i < len(colors)      else 'other',
            color_code   = color_codes[i].strip() if i < len(color_codes) else '#000000',
            sku          = sku or None,   # None so model.save() auto-generates
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


def _handle_existing_variants(request, post_data, files, existing_variants):
    """
    Update price/stock/color/etc. for variants that already exist.
    Also handles adding new images and deleting selected images.
    Errors are added directly to messages (request is available here).
    """
    for variant in existing_variants:
        prefix = f'existing_variant_{variant.pk}'

        price_val  = post_data.get(f'{prefix}_price')
        stock_val  = post_data.get(f'{prefix}_stock')
        color      = post_data.get(f'{prefix}_color',      variant.color)
        color_code = post_data.get(f'{prefix}_color_code', variant.color_code)
        case_type  = post_data.get(f'{prefix}_case_type',  variant.case_type)
        is_active  = f'{prefix}_is_active' in post_data

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
            messages.error(
                request,
                f'Variant "{variant.device_model}": Invalid price or stock value.'
            )
            continue

        delete_ids = post_data.getlist(f'{prefix}_delete_images')
        new_imgs   = files.getlist(f'{prefix}_images')

        current_count   = variant.images.count()
        count_after     = (current_count - len(delete_ids)) + len(new_imgs)

        if count_after < 3:
            messages.error(
                request,
                f'Variant "{variant.device_model}": Must keep at least 3 images '
                f'(would have {count_after}).'
            )
            # Do NOT proceed with delete/upload for this variant.
            continue

        # Safe to apply changes.
        if delete_ids:
            variant.images.filter(pk__in=delete_ids).delete()

        for img in new_imgs:
            err = _validate_image(img)
            if err:
                messages.error(request, f'Variant "{variant.device_model}": {err}')
                continue
            VariantImage.objects.create(
                variant    = variant,
                image      = img,
                is_primary = False,
                order      = variant.images.count() + 1,
            )


def _save_new_variants(product, post_data, files):
    """
    Save brand-new variants added during a product edit.
    Returns a list of error strings.
    """
    errors = []

    device_models = post_data.getlist('new_variant_device_model')
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
            errors.append(f'New variant {i + 1}: Device model is required.')
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
            case_type    = case_types[i].strip()  if i < len(case_types)  else '',
            color        = colors[i]              if i < len(colors)      else 'other',
            color_code   = color_codes[i].strip() if i < len(color_codes) else '#000000',
            sku          = sku or None,
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


# ──────────────────────────────────────────
# PRODUCT ADD
# ──────────────────────────────────────────

@staff_member_required(login_url='admin_login')
@never_cache
def product_add(request):
    form = ProductForm()

    if request.method == 'POST':
        form = ProductForm(request.POST)

        if form.is_valid():
            product = form.save()
            _save_specs(product, request.POST)

            variant_errors = _save_variants(product, request.POST, request.FILES)
            if variant_errors:
                # Roll back — product and its cascade-deleted specs are removed.
                product.delete()
                for err in variant_errors:
                    messages.error(request, err)
                # Re-render with the submitted POST data so the user doesn't lose input.
                return render(request, 'admin_panel/product_add.html', {
                    'form':       form,
                    'categories': Category.objects.filter(is_active=True),
                    'post_data':  request.POST,  # template can use this to repopulate variant fields
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
    product           = get_object_or_404(Product, pk=pk)
    existing_variants = product.variants.prefetch_related('images').all()

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)

        if form.is_valid():
            product = form.save()
            _save_specs(product, request.POST)

            # Update existing variants (request is passed so messages work correctly).
            _handle_existing_variants(request, request.POST, request.FILES, existing_variants)

            # Add any brand-new variants submitted in the same form.
            new_errors = _save_new_variants(product, request.POST, request.FILES)
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


# ══════════════════════════════════════════
# VARIANT AJAX VIEWS
# ══════════════════════════════════════════

@staff_member_required(login_url='admin_login')
@require_POST
def variant_toggle_status(request, pk):
    """Soft activate/deactivate a variant via AJAX."""
    variant = get_object_or_404(ProductVariant, pk=pk)
    variant.is_active = not variant.is_active
    variant.save()
    msg = 'Variant activated.' if variant.is_active else 'Variant deactivated.'
    return JsonResponse({
        'success':   True,
        'message':   msg,
        'is_active': variant.is_active,
    })