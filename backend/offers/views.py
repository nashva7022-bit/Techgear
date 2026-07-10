from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import datetime

from .models import ProductOffer, CategoryOffer
from products.models import Product, Category
from django.conf import settings
from django.core.paginator import Paginator
from itertools import chain


@staff_member_required(login_url='admin_login')
@never_cache
def offer_list(request):
    product_offers = ProductOffer.objects.select_related('product').order_by('-created_at')
    category_offers = CategoryOffer.objects.select_related('category').order_by('-created_at')

    offers = sorted(
        chain(product_offers, category_offers),
        key=lambda x: x.created_at,
        reverse=True
    )
    today = timezone.now().date()

    live_product_offers = product_offers.filter(
        is_active=True, start_date__lte=today, end_date__gte=today
    ).count()
    live_category_offers = category_offers.filter(
        is_active=True, start_date__lte=today, end_date__gte=today
    ).count()
    live_count = live_product_offers + live_category_offers

    product_paginator = Paginator(product_offers, settings.OFFERS_PER_PAGE)
    product_page_obj = product_paginator.get_page(
        request.GET.get('product_page')
    )

    category_paginator = Paginator(category_offers, settings.OFFERS_PER_PAGE)
    category_page_obj = category_paginator.get_page(
        request.GET.get('category_page')
    )


    context = {
        'product_offers': product_page_obj,
        'category_offers': category_page_obj,
        'product_page_obj': product_page_obj,
        'category_page_obj': category_page_obj,
        'today': today,
        'live_count': live_count,
    }
    return render(request, 'offers/offer_list.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def product_offer_create(request):
    products = Product.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        product_id = request.POST.get('product')
        discount_percent = request.POST.get('discount_percent', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        # product validation
        if not product_id:
            field_errors['product'] = 'Please select a product.'

        # discount validation
        try:
            dp = float(discount_percent) if discount_percent else 0
        except ValueError:
            dp = 0

        if not discount_percent or not (0 < dp <= 90):
            field_errors['discount_percent'] = 'Must be between 1% and 90%.'

        # required date validation
        if not start_date:
            field_errors['start_date'] = 'Start date is required.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'

        # date validation only if both dates entered
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start < today:
                    field_errors['start_date'] = 'Start date cannot be in the past.'

                if end < start:
                    field_errors['end_date'] = 'End date must be after start date.'

            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not field_errors:
            product = get_object_or_404(Product, pk=product_id)

            offer, created = ProductOffer.objects.update_or_create(
                product=product,
                defaults={
                    'discount_percent': discount_percent,
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_active': True,
                }
            )

            if created:
                messages.success(request, f'Offer created for "{product.name}".')
            else:
                messages.success(request, f'Offer updated for "{product.name}".')

            return redirect('offers:offer_list')

        return render(request, 'offers/product_offer_form.html', {
            'products': products,
            'field_errors': field_errors,
            'submitted': request.POST,
        })

    return render(request, 'offers/product_offer_form.html', {
        'products': products,
    })


@staff_member_required(login_url='admin_login')
@never_cache
def category_offer_create(request):
    categories = Category.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        category_id = request.POST.get('category')
        discount_percent = request.POST.get('discount_percent', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        # category validation
        if not category_id:
            field_errors['category'] = 'Please select a category.'

        # discount validation
        try:
            dp = float(discount_percent) if discount_percent else 0
        except ValueError:
            dp = 0

        if not discount_percent or not (0 < dp <= 90):
            field_errors['discount_percent'] = 'Must be between 1% and 90%.'

        # required date validation
        if not start_date:
            field_errors['start_date'] = 'Start date is required.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'

        # date validation only if both dates entered
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start < today:
                    field_errors['start_date'] = 'Start date cannot be in the past.'

                if end < start:
                    field_errors['end_date'] = 'End date must be after start date.'

            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not field_errors:
            category = get_object_or_404(Category, pk=category_id)

            offer, created = CategoryOffer.objects.update_or_create(
                category=category,
                defaults={
                    'discount_percent': discount_percent,
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_active': True,
                }
            )

            if created:
                messages.success(request, f'Offer created for "{category.name}".')
            else:
                messages.success(request, f'Offer updated for "{category.name}".')

            return redirect('offers:offer_list')

        return render(request, 'offers/category_offer_form.html', {
            'categories': categories,
            'field_errors': field_errors,
            'submitted': request.POST,
        })

    return render(request, 'offers/category_offer_form.html', {
        'categories': categories
    })


@staff_member_required(login_url='admin_login')
@require_POST
def toggle_product_offer(request, pk):
    offer = get_object_or_404(ProductOffer, pk=pk)
    offer.is_active = not offer.is_active
    offer.save()
    state = 'activated' if offer.is_active else 'deactivated'
    messages.success(request, f'Offer {state}.')
    return redirect('offers:offer_list')


@staff_member_required(login_url='admin_login')
@require_POST
def toggle_category_offer(request, pk):
    offer = get_object_or_404(CategoryOffer, pk=pk)
    offer.is_active = not offer.is_active
    offer.save()
    state = 'activated' if offer.is_active else 'deactivated'
    messages.success(request, f'Offer {state}.')
    return redirect('offers:offer_list')


@staff_member_required(login_url='admin_login')
@require_POST
def delete_product_offer(request, pk):
    offer = get_object_or_404(ProductOffer, pk=pk)
    offer.delete()
    messages.success(request, 'Product offer deleted.')
    return redirect('offers:offer_list')


@staff_member_required(login_url='admin_login')
@require_POST
def delete_category_offer(request, pk):
    offer = get_object_or_404(CategoryOffer, pk=pk)
    offer.delete()
    messages.success(request, 'Category offer deleted.')
    return redirect('offers:offer_list')





@staff_member_required(login_url='admin_login')
@never_cache
def product_offer_edit(request, pk):
    offer = get_object_or_404(ProductOffer.objects.select_related('product'), pk=pk)

    if request.method == 'POST':
        discount_percent = request.POST.get('discount_percent', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        try:
            dp = float(discount_percent) if discount_percent else 0
        except ValueError:
            dp = 0

        if not discount_percent or not (0 < dp <= 90):
            field_errors['discount_percent'] = 'Must be between 1% and 90%.'

        if not start_date:
            field_errors['start_date'] = 'Start date is required.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'

        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()

                if end < start:
                    field_errors['end_date'] = 'End date must be after start date.'

            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not field_errors:
            offer.discount_percent = discount_percent
            offer.start_date = start_date
            offer.end_date = end_date
            offer.save()

            messages.success(request, f'Offer updated for "{offer.product.name}".')
            return redirect('offers:offer_list')

        return render(request, 'offers/product_offer_form.html', {
            'offer': offer,
            'field_errors': field_errors,
            'submitted': request.POST,
            'is_edit': True,
        })

    return render(request, 'offers/product_offer_form.html', {
        'offer': offer,
        'is_edit': True,
    })


@staff_member_required(login_url='admin_login')
@never_cache
def category_offer_edit(request, pk):
    offer = get_object_or_404(CategoryOffer.objects.select_related('category'), pk=pk)

    if request.method == 'POST':
        discount_percent = request.POST.get('discount_percent', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        try:
            dp = float(discount_percent) if discount_percent else 0
        except ValueError:
            dp = 0

        if not discount_percent or not (0 < dp <= 90):
            field_errors['discount_percent'] = 'Must be between 1% and 90%.'

        if not start_date:
            field_errors['start_date'] = 'Start date is required.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'

        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()

                if end < start:
                    field_errors['end_date'] = 'End date must be after start date.'

            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not field_errors:
            offer.discount_percent = discount_percent
            offer.start_date = start_date
            offer.end_date = end_date
            offer.save()

            messages.success(request, f'Offer updated for "{offer.category.name}".')
            return redirect('offers:offer_list')

        return render(request, 'offers/category_offer_form.html', {
            'offer': offer,
            'field_errors': field_errors,
            'submitted': request.POST,
            'is_edit': True,
        })

    return render(request, 'offers/category_offer_form.html', {
        'offer': offer,
        'is_edit': True,
    })