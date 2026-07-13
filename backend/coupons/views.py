from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator

from .models import Coupon

@staff_member_required(login_url='admin_login')
@never_cache
def coupon_list(request):
    coupons = Coupon.objects.all().order_by('-created_at')
    today   = timezone.now().date()#checks validity


    paginator   = Paginator(coupons, settings.COUPONS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
    context = {
        'coupons':      page_obj,
        'page_obj':     page_obj,
        'today':        today,
        'active_count': sum(1 for c in coupons if c.is_currently_valid),
        'total_uses':   sum(c.times_used for c in coupons),
    }
    return render(request, 'coupons/coupon_list.html', context)


from datetime import datetime

@staff_member_required(login_url='admin_login')
@never_cache
def coupon_create(request):
    if request.method == 'POST':
        code             = request.POST.get('code', '').strip().upper()
        description      = request.POST.get('description', '').strip()
        discount_type    = request.POST.get('discount_type', '').strip()
        discount_value   = request.POST.get('discount_value', '').strip()
        max_discount_cap = request.POST.get('max_discount_cap', '').strip()
        min_order_amount = request.POST.get('min_order_amount', '').strip()
        usage_limit      = request.POST.get('usage_limit', '').strip()
        start_date       = request.POST.get('start_date', '').strip()
        end_date         = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        # Code validation 
        if not code:
            field_errors['code'] = 'Coupon code is required.'
        elif Coupon.objects.filter(code__iexact=code).exists():
            field_errors['code'] = 'A coupon with this code already exists.'

        #Discount type validation
        if discount_type not in ('percentage', 'fixed'):
            field_errors['discount_type'] = 'Please select a discount type.'

        # Discount value validation 
        dv = None
        try:
            dv = float(discount_value)
            if dv <= 0:
                field_errors['discount_value'] = 'Discount value must be greater than 0.'
            elif discount_type == 'percentage' and dv > 90:
                field_errors['discount_value'] = 'Percentage discount cannot exceed 90%.'
            elif discount_type == 'fixed' and dv > 10000:
                field_errors['discount_value'] = 'Fixed discount cannot exceed ₹10,000.'
        except (ValueError, TypeError):
            field_errors['discount_value'] = 'Enter a valid discount value.'

        # Max discount cap validation 
        if max_discount_cap:
            if discount_type == 'fixed':
                field_errors['max_discount_cap'] = 'Max cap only applies to percentage discounts.'
            else:
                try:
                    mc = float(max_discount_cap)
                    if mc <= 0:
                        field_errors['max_discount_cap'] = 'Enter a valid amount greater than 0.'
                    elif dv and discount_type == 'percentage':
                        
                        if mc > 10000:
                            field_errors['max_discount_cap'] = 'Cap cannot exceed ₹10,000.'
                except (ValueError, TypeError):
                    field_errors['max_discount_cap'] = 'Enter a valid amount.'

        #  Min order amount validation 
        if min_order_amount:
            try:
                moa = float(min_order_amount)
                if moa < 0:
                    field_errors['min_order_amount'] = 'Minimum order amount cannot be negative.'
                elif moa > 100000:
                    field_errors['min_order_amount'] = 'Minimum order amount seems too high.'
            except (ValueError, TypeError):
                field_errors['min_order_amount'] = 'Enter a valid amount.'
        else:
            min_order_amount = 0

        #  Usage limit validation 
        if usage_limit:
            try:
                ul = int(usage_limit)
                if ul <= 0:
                    field_errors['usage_limit'] = 'Usage limit must be at least 1.'
                elif ul > 100000:
                    field_errors['usage_limit'] = 'Usage limit seems too high.'
            except (ValueError, TypeError):
                field_errors['usage_limit'] = 'Enter a valid whole number.'

        # Date validation 
        parsed_start = None
        parsed_end   = None

        if not start_date:
            field_errors['start_date'] = 'Start date is required.'
        else:
            try:
                parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
                if parsed_start < today:
                    field_errors['start_date'] = 'Start date cannot be in the past.'
            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'
        else:
            try:
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                field_errors['end_date'] = 'Invalid date format.'

        
        if parsed_start and parsed_end:
            if parsed_end < parsed_start:
                field_errors['end_date'] = 'End date must be after start date.'
            elif parsed_end == parsed_start:
                field_errors['end_date'] = 'End date must be after start date, not the same day.'

       
        if not field_errors:
            Coupon.objects.create(
                code             = code,
                description      = description,
                discount_type    = discount_type,
                discount_value   = discount_value,
                max_discount_cap = max_discount_cap or None,
                min_order_amount = min_order_amount,
                usage_limit      = usage_limit or None,
                start_date       = start_date,
                end_date         = end_date,
                is_active        = True,
            )
            messages.success(request, f'Coupon "{code}" created successfully.')
            return redirect('coupons:coupon_list')

        return render(request, 'coupons/coupon_form.html', {
            'field_errors': field_errors,
            'submitted': request.POST,
            'coupon': None,
            'edit_mode': False,
    })

    return render(request, 'coupons/coupon_form.html', {
        'coupon': None,
        'edit_mode': False,
    })

@staff_member_required(login_url='admin_login')
@never_cache
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)

    if request.method == 'POST':
        code             = request.POST.get('code', '').strip().upper()
        description      = request.POST.get('description', '').strip()
        discount_type    = request.POST.get('discount_type', '').strip()
        discount_value   = request.POST.get('discount_value', '').strip()
        max_discount_cap = request.POST.get('max_discount_cap', '').strip()
        min_order_amount = request.POST.get('min_order_amount', '').strip()
        usage_limit      = request.POST.get('usage_limit', '').strip()
        start_date       = request.POST.get('start_date', '').strip()
        end_date         = request.POST.get('end_date', '').strip()

        field_errors = {}
        today = timezone.now().date()

        if not code:
            field_errors['code'] = 'Coupon code is required.'
        elif Coupon.objects.filter(code__iexact=code).exclude(pk=pk).exists():
            field_errors['code'] = 'A coupon with this code already exists.'

        if discount_type not in ('percentage', 'fixed'):
            field_errors['discount_type'] = 'Please select a discount type.'

        dv = None
        try:
            dv = float(discount_value)
            if dv <= 0:
                field_errors['discount_value'] = 'Discount value must be greater than 0.'
            elif discount_type == 'percentage' and dv > 90:
                field_errors['discount_value'] = 'Percentage discount cannot exceed 90%.'
            elif discount_type == 'fixed' and dv > 10000:
                field_errors['discount_value'] = 'Fixed discount cannot exceed ₹10,000.'
        except (ValueError, TypeError):
            field_errors['discount_value'] = 'Enter a valid discount value.'

        if max_discount_cap:
            if discount_type == 'fixed':
                field_errors['max_discount_cap'] = 'Max cap only applies to percentage discounts.'
            else:
                try:
                    mc = float(max_discount_cap)
                    if mc <= 0:
                        field_errors['max_discount_cap'] = 'Enter a valid amount greater than 0.'
                    elif mc > 10000:
                        field_errors['max_discount_cap'] = 'Cap cannot exceed ₹10,000.'
                except (ValueError, TypeError):
                    field_errors['max_discount_cap'] = 'Enter a valid amount.'

        if min_order_amount:
            try:
                moa = float(min_order_amount)
                if moa < 0:
                    field_errors['min_order_amount'] = 'Minimum order amount cannot be negative.'
            except (ValueError, TypeError):
                field_errors['min_order_amount'] = 'Enter a valid amount.'
        else:
            min_order_amount = 0

        if usage_limit:
            try:
                ul = int(usage_limit)
                if ul <= 0:
                    field_errors['usage_limit'] = 'Usage limit must be at least 1.'
                elif ul < coupon.times_used:
                    field_errors['usage_limit'] = f'Cannot set limit below current usage count ({coupon.times_used}).'
            except (ValueError, TypeError):
                field_errors['usage_limit'] = 'Enter a valid whole number.'

        parsed_start = None
        parsed_end   = None

        if not start_date:
            field_errors['start_date'] = 'Start date is required.'
        else:
            try:
                parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                field_errors['start_date'] = 'Invalid date format.'

        if not end_date:
            field_errors['end_date'] = 'End date is required.'
        else:
            try:
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
                if parsed_end < today:
                    field_errors['end_date'] = 'End date cannot be in the past.'
            except ValueError:
                field_errors['end_date'] = 'Invalid date format.'

        if parsed_start and parsed_end:
            if parsed_end < parsed_start:
                field_errors['end_date'] = 'End date must be after start date.'
            elif parsed_end == parsed_start:
                field_errors['end_date'] = 'End date must be after start date, not the same day.'

        if not field_errors:
            coupon.code             = code
            coupon.description      = description
            coupon.discount_type    = discount_type
            coupon.discount_value   = discount_value
            coupon.max_discount_cap = max_discount_cap or None
            coupon.min_order_amount = min_order_amount
            coupon.usage_limit      = usage_limit or None
            coupon.start_date       = start_date
            coupon.end_date         = end_date
            coupon.save()
            messages.success(request, f'Coupon "{code}" updated successfully.')
            return redirect('coupons:coupon_list')

        return render(request, 'coupons/coupon_form.html', {
            'field_errors': field_errors,
            'submitted':    request.POST,
            'coupon':       coupon,
            'edit_mode':    True,
        })

    return render(request, 'coupons/coupon_form.html', {
        'coupon':    coupon,
        'edit_mode': True,
    })


@staff_member_required(login_url='admin_login')
@require_POST
def toggle_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save()
    state = 'activated' if coupon.is_active else 'deactivated'
    messages.success(request, f'Coupon "{coupon.code}" {state}.')
    return redirect('coupons:coupon_list')


@staff_member_required(login_url='admin_login')
@require_POST
def delete_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    code   = coupon.code
    coupon.delete()
    messages.success(request, f'Coupon "{code}" deleted.')
    return redirect('coupons:coupon_list')