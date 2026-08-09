from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import CouponForm
from .models import Coupon


@staff_member_required(login_url="admin_login")
@never_cache
def coupon_list(request):
    coupons = Coupon.objects.all().order_by("-created_at")
    today = timezone.now().date()

    paginator = Paginator(coupons, settings.COUPONS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "coupons": page_obj,
        "page_obj": page_obj,
        "today": today,
        "active_count": sum(1 for c in coupons if c.is_currently_valid),
        "total_uses": sum(c.times_used for c in coupons),
    }
    return render(request, "coupons/coupon_list.html", context)


@staff_member_required(login_url="admin_login")
@never_cache
def coupon_create(request):
    if request.method == "POST":
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'Coupon "{form.cleaned_data["code"]}" created successfully.'
            )
            return redirect("coupons:coupon_list")
        return render(
            request,
            "coupons/coupon_form.html",
            {
                "form": form,
                "coupon": None,
                "edit_mode": False,
            },
        )

    form = CouponForm()
    return render(
        request,
        "coupons/coupon_form.html",
        {
            "form": form,
            "coupon": None,
            "edit_mode": False,
        },
    )


@staff_member_required(login_url="admin_login")
@never_cache
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)

    if request.method == "POST":
        form = CouponForm(request.POST, instance=coupon, is_edit=True)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'Coupon "{form.cleaned_data["code"]}" updated successfully.'
            )
            return redirect("coupons:coupon_list")
        return render(
            request,
            "coupons/coupon_form.html",
            {
                "form": form,
                "coupon": coupon,
                "edit_mode": True,
            },
        )

    form = CouponForm(instance=coupon, is_edit=True)
    return render(
        request,
        "coupons/coupon_form.html",
        {
            "form": form,
            "coupon": coupon,
            "edit_mode": True,
        },
    )


@staff_member_required(login_url="admin_login")
@require_POST
def toggle_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save()
    state = "activated" if coupon.is_active else "deactivated"
    messages.success(request, f'Coupon "{coupon.code}" {state}.')
    return redirect("coupons:coupon_list")


@staff_member_required(login_url="admin_login")
@require_POST
def delete_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    code = coupon.code
    coupon.delete()
    messages.success(request, f'Coupon "{code}" deleted.')
    return redirect("coupons:coupon_list")
