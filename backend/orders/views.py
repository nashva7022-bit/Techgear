
from __future__ import annotations
import logging#instead of print
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from offers.utils import get_effective_price
from store.models import Cart, Review
from users.forms import AddressForm
from users.models import Address
from weasyprint import HTML
from .models import Order, OrderItem, OrderStatusLog
from .services import (
    cancel_order,
    cancel_order_item,
    place_cod_order,
    place_razorpay_order,
    return_order_item,
    verify_razorpay_payment,
)

logger = logging.getLogger(__name__)



def _build_checkout_context(request, cart, cart_items, addresses, wallet_balance):
    
    from coupons.models import Coupon

    
    subtotal = Decimal("0.00")
    total_offer_discount = Decimal("0.00")
    customization_total = Decimal("0.00")
    enriched_items = []

    for item in cart_items:
        #disc price
        eff_price, _ = get_effective_price(item.variant)
        original_price = item.variant.price
        item_offer_discount = (original_price - eff_price) * item.quantity
        item_discounted_total = (eff_price * item.quantity) + (
            item.customization_charge * item.quantity
        )

        subtotal += item_discounted_total
        total_offer_discount += item_offer_discount
        customization_total += item.customization_charge * item.quantity

        discount_pct = 0
        if original_price > 0:
            discount_pct = round(
                ((original_price - eff_price) / original_price) * 100
            )

        enriched_items.append(
            {
                "item": item,
                "effective_price": eff_price,
                "discounted_total": item_discounted_total,
                "discount_pct": discount_pct,
                
                "variant": item.variant,
                "quantity": item.quantity,
                "customization_charge": item.customization_charge,
            }
        )

    shipping_charge = Decimal("0.00")
    #cart total
    pre_coupon_total = subtotal + shipping_charge
    original_product_total = subtotal - customization_total + total_offer_discount

     
    applied_coupon = request.session.get("applied_coupon")
    coupon_code = ""
    coupon_discount = Decimal("0.00")

    if applied_coupon:
        coupon_code = applied_coupon.get("code", "")
       
        try:
            raw_discount = Decimal(str(applied_coupon.get("discount", "0")))
            coupon_discount = min(raw_discount, pre_coupon_total)
        except Exception:
            request.session.pop("applied_coupon", None)
            #resets
            coupon_code = ""
            coupon_discount = Decimal("0.00")

    total_amount = max(Decimal("0.00"), pre_coupon_total - coupon_discount)

    #  Wallet 
    wallet_applicable = min(wallet_balance, total_amount)

    
    from coupons.utils import validate_coupon

    now_coupons = Coupon.objects.filter(is_active=True)
    available_coupons = []

    for c in now_coupons:
        _, error = validate_coupon(c.code, request.user, pre_coupon_total)
        applicable = error is None
        amount_needed = Decimal("0.00")
        if not applicable and c.min_order_amount:
            amount_needed = max(
                Decimal("0.00"), c.min_order_amount - pre_coupon_total
            )
            
        available_coupons.append(
            {
                "code": c.code,
                "discount_type": c.discount_type,
                "discount_value": c.discount_value,
                "max_discount_cap": getattr(c, "max_discount_cap", None),
                "min_order_amount": c.min_order_amount,
                "end_date": c.end_date,
                "description": getattr(c, "description", ""),
                "applicable": applicable,
                "amount_needed": amount_needed,
            }
        )

    return {
        # Cart
        "cart_items": enriched_items,
        "cart": cart,
        # Address
        "addresses": addresses,
        "address_form": AddressForm(),
        # Totals
        "subtotal": subtotal,
        "original_product_total": original_product_total,
        "total_offer_discount": total_offer_discount,
        "customization_total": customization_total,
        "shipping_charge": shipping_charge,
        "coupon_code": coupon_code,
        "coupon_discount": coupon_discount,
        "total_amount": total_amount,
        # Wallet
        "wallet_balance": wallet_balance,
        "wallet_applicable": wallet_applicable,
        # Coupons
        "available_coupons": available_coupons,
    }


def _get_wallet_balance(user):
    from wallet.models import Wallet

    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet.balance



@login_required
@never_cache
def checkout(request):
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

   
    cart_items = list(
        cart.items.select_related(
            "variant__product__category",
            "variant__device_model",
        ).prefetch_related("variant__images")
    )
    addresses = request.user.addresses.all().order_by("-is_default", "-created_at")
    wallet_balance = _get_wallet_balance(request.user)

    
    if request.method == "POST":
        action = request.POST.get("action", "")#treat it as an empty string
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # ADD ADDRESS
        if action == "add_address":
            form = AddressForm(request.POST)
            if form.is_valid():
                addr = form.save(commit=False)
                addr.user = request.user
                addr.save()
                
                if request.user.addresses.count() == 1:
                    addr.is_default = True
                    addr.save(update_fields=["is_default"])
                return JsonResponse(
                    {
                        "ok": True,
                        "message": "Address added successfully.",
                        "address": _serialize_address(addr),
                    }
                )
            
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        # EDIT ADDRESS
        if action == "edit_address":
            addr_id = request.POST.get("editing_address_id", "")
            addr = get_object_or_404(Address, pk=addr_id, user=request.user)
            form = AddressForm(request.POST, instance=addr)
            if form.is_valid():
                form.save()
                addr.refresh_from_db()
                return JsonResponse(
                    {
                        "ok": True,
                        "message": "Address updated.",
                        "address": _serialize_address(addr),
                    }
                )
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

       
        if action == "delete_address":
            addr_id = request.POST.get("address_id", "")
            addr = Address.objects.filter(pk=addr_id, user=request.user).first()
            if not addr:
                return JsonResponse(
                    {"ok": False, "error": "Address not found."}, status=404
                )
            addr.delete()
            return JsonResponse({"ok": True, "message": "Address deleted."})

        # PLACE ORDER 
        if action == "place_order":
            address_id = request.POST.get("selected_address", "")
            if not address_id:
                messages.error(request, "Please select a delivery address.")
                
                return render(
                    request,
                    "orders/checkout.html",
                    _build_checkout_context(
                        request, cart, cart_items, addresses, wallet_balance
                    ),
                )

            address = get_object_or_404(Address, pk=address_id, user=request.user)
            use_wallet = request.POST.get("use_wallet") == "1"
            payment_method = request.POST.get("payment_method", "cod")
            applied_coupon = request.session.get("applied_coupon")
            coupon_code = applied_coupon.get("code") if applied_coupon else None

            if payment_method == "razorpay":
                try:
                    order_or_none, razorpay_data = place_razorpay_order(
                        user=request.user,
                        cart=cart,
                        address=address,
                        use_wallet=use_wallet,
                        coupon_code=coupon_code,
                    )

                
                    if razorpay_data is None and order_or_none is not None:#wallet coveres full
                        request.session.pop("applied_coupon", None)
                        return redirect(
                            "orders:order_success",
                            order_number=order_or_none.order_number,
                        )

                    if razorpay_data is not None:#wall havent cover full
                        rp_order = razorpay_data["razorpay_order"]
                        
                        razorpay_order_id = (
                            rp_order["id"]
                            if isinstance(rp_order, dict)
                            else rp_order.id
                        )
                        request.session["pending_razorpay"] = {
                            "address_id": address.pk,
                            "use_wallet": use_wallet,
                            "coupon_code": coupon_code,
                            "wallet_deduction": str(
                                razorpay_data["wallet_deduction"]
                            ),
                            "razorpay_amount": str(
                                razorpay_data["razorpay_amount"]
                            ),
                            "razorpay_order_id": razorpay_order_id,
                        }
                        return render(
                            request,
                            "orders/razorpay_payment.html",
                            {
                                "razorpay_order": rp_order,
                                "razorpay_key": settings.RAZORPAY_KEY_ID,
                                "amount": int(
                                    Decimal(str(razorpay_data["razorpay_amount"]))
                                    * 100
                                ),
                                "order_number": razorpay_order_id,
                                "user_name": request.user.get_full_name()
                                or request.user.email,
                                "user_email": request.user.email,
                                "user_phone": address.phone,
                            },
                        )

                    
                    messages.error(
                        request, "Could not initialise payment. Please try again."
                    )
                    return redirect("orders:checkout")

                except ValueError as exc:
                    messages.error(request, str(exc))
                    return render(
                        request,
                        "orders/checkout.html",
                        _build_checkout_context(
                            request, cart, cart_items, addresses, wallet_balance
                        ),
                    )

            else:  # COD
                try:
                    order = place_cod_order(
                        user=request.user,
                        cart=cart,
                        address=address,
                        use_wallet=use_wallet,
                        coupon_code=coupon_code,
                    )
                    request.session.pop("applied_coupon", None)
                    return redirect(
                        "orders:order_success", order_number=order.order_number
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return render(
                        request,
                        "orders/checkout.html",
                        _build_checkout_context(
                            request, cart, cart_items, addresses, wallet_balance
                        ),
                    )

    
        logger.warning(
            "checkout: unknown action=%r from user=%s", action, request.user.pk
        )
        return render(
            request,
            "orders/checkout.html",
            _build_checkout_context(
                request, cart, cart_items, addresses, wallet_balance
            ),
        )

    return render(
        request,
        "orders/checkout.html",
        _build_checkout_context(
            request, cart, cart_items, addresses, wallet_balance
        ),
    )


def _serialize_address(addr):
  
    return {
        "id": addr.pk,
        "label": addr.address_label,
        "name": addr.full_name,
        "line1": addr.address_line_1,
        "line2": addr.address_line_2 or "",
        "city": addr.city,
        "state": addr.state,
        "postal": addr.postal_code,
        "country": addr.country,
        "phone": addr.phone,
        "is_default": addr.is_default,
    }


# ORDER SUCCESS


@login_required
@never_cache
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    offer_discount = order.discount_amount - order.coupon_discount

    return render(
    request,
    "orders/order_success.html",
    {
        "order": order,
        "offer_discount": offer_discount,
    }
)


# ORDER LIST


@login_required
@never_cache
def order_list(request):
    search = request.GET.get("search", "").strip()
    orders = Order.objects.filter(user=request.user).prefetch_related("items")

    if search:
        orders = orders.filter(
            Q(order_number__icontains=search)
            | Q(items__product_name__icontains=search)
        ).distinct()

    paginator = Paginator(orders, getattr(settings, "ORDERS_PER_PAGE", 10))
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "orders/order_list.html",
        {"page_obj": page_obj, "search": search},
    )



# ORDER DETAIL


@login_required
@never_cache
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    items = order.items.select_related("variant").prefetch_related("variant__images")
    status_logs = order.status_logs.all()
    offer_discount = order.discount_amount - order.coupon_discount


    customization_total = sum(
        item.customization_charge
        for item in items
    )   

    original_product_total = (
        order.subtotal
        + offer_discount
        +order.coupon_discount
        - customization_total
    )      

    reviewed_product_ids = set(
        Review.objects.filter(user=request.user).values_list("product_id", flat=True)
    )

    return render(
    request,
    "orders/order_detail.html",
    {
        "order": order,
        "items": items,
        "status_logs": status_logs,
        "reviewed_product_ids": reviewed_product_ids,

        "offer_discount": offer_discount,
        "customization_total": customization_total,
        "original_product_total": original_product_total,
    },
)


# CANCEL ENTIRE ORDER


@login_required
@require_POST
def cancel_order_view(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    reason = request.POST.get("reason", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        cancel_order(order=order, cancelled_by=request.user, reason=reason)
        if is_ajax:
            return JsonResponse(
                {
                    "ok": True,
                    "message": "Order cancelled successfully.",
                    "status": "cancelled",
                }
            )
        messages.success(request, "Your order has been cancelled.")
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))

    return redirect("orders:order_detail", order_number=order_number)


# CANCEL SINGLE ITEM


@login_required
@require_POST
def cancel_item_view(request, order_number, item_id):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    reason = request.POST.get("reason", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        cancel_order_item(order_item=item, cancelled_by=request.user, reason=reason)
        msg = f'"{item.product_name}" has been cancelled.'
        if is_ajax:
            return JsonResponse({"ok": True, "message": msg, "status": "cancelled"})
        messages.success(request, msg)
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))

    return redirect("orders:order_detail", order_number=order_number)



# RETURN SINGLE ITEM


@login_required
@require_POST
def return_item_view(request, order_number, item_id):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    reason = request.POST.get("reason", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not reason:
        err = "Please provide a reason for the return."
        if is_ajax:
            return JsonResponse({"ok": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect("orders:order_detail", order_number=order_number)

    try:
        return_order_item(order_item=item, returned_by=request.user, reason=reason)
        msg = f'Return request for "{item.product_name}" submitted.'
        if is_ajax:
            return JsonResponse(
                {"ok": True, "message": msg, "status": "return_requested"}
            )
        messages.success(request, msg)
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))

    return redirect("orders:order_detail", order_number=order_number)



# PDF INVOICE


@login_required
def download_invoice(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if order.status not in ("delivered", "cancelled"):
        messages.error(
            request,
            "Invoice is only available for delivered or cancelled orders.",
        )
        return redirect("orders:order_detail", order_number=order_number)

    items = order.items.all()

    offer_discount = order.discount_amount - order.coupon_discount

    customization_total = sum(
        item.customization_charge
        for item in items
    )

    original_product_total = (
        order.subtotal
        + offer_discount
        + order.coupon_discount
        - customization_total
    )

    html_string = render_to_string(
        "orders/invoice.html",
        {
            "order": order,
            "items": items,
            "status_logs": order.status_logs.all(),

            "offer_discount": offer_discount,
            "customization_total": customization_total,
            "original_product_total": original_product_total,
        },
    )
    pdf = HTML(
        string=html_string,
        base_url=getattr(settings, "STATIC_ROOT", None),
    ).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="Invoice-{order.order_number}.pdf"'
    )
    return response



# COUPON — APPLY


@login_required
@require_POST
def apply_coupon(request):
    from coupons.utils import calculate_coupon_discount, validate_coupon

    code = request.POST.get("code", "").strip().upper()
    if not code:
        return JsonResponse({"ok": False, "error": "Please enter a coupon code."})

    
    if request.session.get("applied_coupon"):
        return JsonResponse(
            {
                "ok": False,
                "error": "A coupon is already applied. Remove it before applying another.",
            }
        )

    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        return JsonResponse({"ok": False, "error": "Your cart is empty."})

    subtotal = Decimal("0.00")
    for item in cart.items.select_related("variant__product__category"):
        eff_price, _ = get_effective_price(item.variant)
        subtotal += (eff_price * item.quantity) + (
            item.customization_charge * item.quantity
        )

    shipping = Decimal("0.00")
    order_total = subtotal + shipping

    coupon, error = validate_coupon(code, request.user, order_total)
    if error:
        return JsonResponse({"ok": False, "error": error})

    discount = calculate_coupon_discount(coupon, order_total)
    
    discount = min(discount, order_total)

    request.session["applied_coupon"] = {
        "code": coupon.code,
        "discount": str(discount),
    }
   
    request.session.modified = True

    return JsonResponse(
        {
            "ok": True,
            "code": coupon.code,
            "discount": str(discount),
            "message": f"Coupon applied! You save ₹{discount}",
        }
    )



# COUPON — REMOVE


@login_required
@require_POST
def remove_coupon(request):
    request.session.pop("applied_coupon", None)
    request.session.modified = True
    return JsonResponse({"ok": True})



# RAZORPAY CALLBACK


@csrf_exempt
@login_required
def razorpay_callback(request):
  
    if request.method not in ("POST", "GET"):
        return redirect("orders:checkout")

    
    data = request.POST if request.method == "POST" else request.GET
    razorpay_payment_id = data.get("razorpay_payment_id", "")
    razorpay_order_id = data.get("razorpay_order_id", "")
    razorpay_signature = data.get("razorpay_signature", "")

    logger.info(#save payment log
        "razorpay_callback: user=%s payment_id=%s order_id=%s",
        request.user.pk,
        razorpay_payment_id,
        razorpay_order_id,
    )

    pending = request.session.get("pending_razorpay")

    
    if not pending or pending.get("razorpay_order_id") != razorpay_order_id:
        logger.warning(
            "razorpay_callback: session mismatch for user=%s order_id=%s",
            request.user.pk,
            razorpay_order_id,
        )
        messages.error(
            request,
            "Payment session expired or invalid. If your payment was deducted, "
            "it will be refunded automatically within 5-7 business days.",
        )
        return redirect("orders:checkout")

    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        
        pass

    address = get_object_or_404(
        Address, pk=pending["address_id"], user=request.user
    )

    try:
        order = verify_razorpay_payment(
            user=request.user,
            cart=cart,
            address=address,
            session_data=pending,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_signature=razorpay_signature,
        )
        
        request.session.pop("pending_razorpay", None)
        request.session.pop("applied_coupon", None)
        request.session.modified = True
        return redirect("orders:order_success", order_number=order.order_number)

    except ValueError as exc:
        error_msg = str(exc)
        
        request.session.pop("pending_razorpay", None)
        request.session.modified = True

        if "refund" in error_msg.lower():
            
            request.session["failed_payment_amount"] = pending.get(
                "razorpay_amount", "0"
            )
            messages.error(request, error_msg)
            return redirect("orders:payment_failed")

        messages.error(request, error_msg)
        return redirect("orders:checkout")


# PAYMENT FAILED


@login_required
@never_cache
def payment_failed(request):
    
    amount = request.session.pop("failed_payment_amount", None)
    return render(request, "orders/payment_failed.html", {"amount": amount})



# RAZORPAY PAYMENT FAILED 


@login_required
@require_POST
def razorpay_payment_failed(request):
    
    pending = request.session.get("pending_razorpay", {})
    request.session["failed_payment_amount"] = pending.get("razorpay_amount", "0")
    request.session.pop("pending_razorpay", None)
    request.session.modified = True
    return JsonResponse({"ok": True})