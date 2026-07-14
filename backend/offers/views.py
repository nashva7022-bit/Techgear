
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from .models import ProductOffer, CategoryOffer
from products.models import Product, Category
from django.conf import settings
from django.core.paginator import Paginator
from itertools import chain

from .forms import CategoryOfferForm,ProductOfferForm

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
        'offers':offers
    }
    return render(request, 'offers/offer_list.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
def product_offer_create(request):
    if request.method == 'POST':
        form = ProductOfferForm(request.POST)
        form.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')
        if form.is_valid():
            offer = form.save()
            messages.success(request, f'Offer created for "{offer.product.name}".')
            return redirect('offers:offer_list')
        return render(request, 'offers/product_offer_form.html', {'form': form})

    form = ProductOfferForm()
    form.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')
    return render(request, 'offers/product_offer_form.html', {'form': form})


@staff_member_required(login_url='admin_login')
@never_cache
def product_offer_edit(request, pk):
    offer = get_object_or_404(ProductOffer.objects.select_related('product'), pk=pk)

    if request.method == 'POST':
        form = ProductOfferForm(request.POST, instance=offer, is_edit=True)
        if form.is_valid():
            form.save()
            messages.success(request, f'Offer updated for "{offer.product.name}".')
            return redirect('offers:offer_list')
        return render(request, 'offers/product_offer_form.html', {
            'form': form, 'offer': offer, 'is_edit': True,
        })

    form = ProductOfferForm(instance=offer, is_edit=True)
    return render(request, 'offers/product_offer_form.html', {
        'form': form, 'offer': offer, 'is_edit': True,
    })
@staff_member_required(login_url='admin_login')
@never_cache
def category_offer_create(request):
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST)
        form.fields['category'].queryset = Category.objects.filter(is_active=True).order_by('name')
        if form.is_valid():
            offer = form.save()
            messages.success(request, f'Offer created for "{offer.category.name}".')
            return redirect('offers:offer_list')
        return render(request, 'offers/category_offer_form.html', {'form': form})

    form = CategoryOfferForm()
    form.fields['category'].queryset = Category.objects.filter(is_active=True).order_by('name')
    return render(request, 'offers/category_offer_form.html', {'form': form})


@staff_member_required(login_url='admin_login')
@never_cache
def category_offer_edit(request, pk):
    offer = get_object_or_404(CategoryOffer.objects.select_related('category'), pk=pk)

    if request.method == 'POST':
        form = CategoryOfferForm(request.POST, instance=offer, is_edit=True)
        if form.is_valid():
            form.save()
            messages.success(request, f'Offer updated for "{offer.category.name}".')
            return redirect('offers:offer_list')
        return render(request, 'offers/category_offer_form.html', {
            'form': form, 'offer': offer, 'is_edit': True,
        })

    form = CategoryOfferForm(instance=offer, is_edit=True)
    return render(request, 'offers/category_offer_form.html', {
        'form': form, 'offer': offer, 'is_edit': True,
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




