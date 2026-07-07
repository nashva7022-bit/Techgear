from __future__ import annotations

import logging
from decimal import ROUND_DOWN, Decimal

from django.db import IntegrityError, transaction
from django.db import transaction as db_transaction

from offers.utils import get_effective_price

from .models import VALID_TRANSITIONS, Order, OrderItem, OrderStatusLog

logger = logging.getLogger(__name__)



# PRIVATE HELPERS


def _d(value) -> Decimal:
    
    return Decimal(str(value))


def _snapshot_address(address) -> dict:
    return {
        "shipping_full_name": address.full_name,
        "shipping_phone": address.phone,
        "shipping_address_line_1": address.address_line_1,
        "shipping_address_line_2": address.address_line_2 or "",
        "shipping_city": address.city,
        "shipping_state": address.state,
        "shipping_postal_code": address.postal_code,
        "shipping_country": address.country,
    }


def _snapshot_item(cart_item) -> dict:
    
    variant = cart_item.variant
    product = variant.product
    effective_price, _ = get_effective_price(variant)
    item_subtotal = (effective_price * cart_item.quantity) + (
        _d(cart_item.customization_charge) * cart_item.quantity
    )
    return {
        "variant": variant,
        "product_name": product.name,
        "variant_sku": variant.sku or "",
        "device_model": variant.device_model.name if variant.device_model else "",
        "case_type": variant.get_case_type_display() if variant.case_type else "",
        "color": variant.get_color_display(),
        "color_code": variant.color_code,
        "original_price": variant.price,       # MRP snapshot
        "unit_price": effective_price,          # discounted price snapshot
        "quantity": cart_item.quantity,
        "subtotal": item_subtotal,
        "custom_text": cart_item.custom_text or "",
        "custom_image": cart_item.custom_image or None,
        "customization_charge": _d(cart_item.customization_charge),
    }


def _calculate_totals(cart_items, coupon=None) -> dict:
   
    discounted_subtotal = Decimal("0.00")
    total_offer_discount = Decimal("0.00")
    
    
    for item in cart_items:
        eff_price, _ = get_effective_price(item.variant)
        regular_total = _d(item.variant.price) * item.quantity
        discounted_total = (eff_price * item.quantity) + (
            _d(item.customization_charge) * item.quantity
        )
        discounted_subtotal += discounted_total
        total_offer_discount += regular_total - (eff_price * item.quantity)

    shipping_charge = Decimal("0.00")
    pre_coupon_total = discounted_subtotal + shipping_charge

    coupon_discount = Decimal("0.00")
    if coupon:
        from coupons.utils import calculate_coupon_discount

        coupon_discount = calculate_coupon_discount(coupon, pre_coupon_total)
        
        coupon_discount = min(coupon_discount, pre_coupon_total)

    total_amount = max(Decimal("0.00"), pre_coupon_total - coupon_discount)

    return {
        "subtotal": discounted_subtotal,
        "discount_amount": total_offer_discount + coupon_discount,
        "shipping_charge": shipping_charge,
        "total_amount": total_amount,
        "coupon_code": coupon.code if coupon else "",
        "coupon_discount": coupon_discount,
    }


def _resolve_coupon(coupon_code: str | None, user, cart_items):
   
    if not coupon_code:
        return None

    from coupons.models import Coupon
    from coupons.utils import validate_coupon

    coupon = Coupon.objects.filter(code=coupon_code, is_active=True).first()
    if not coupon:
        return None

    
    temp_totals = _calculate_totals(cart_items, coupon=None)
    _, error = validate_coupon(coupon_code, user, temp_totals["total_amount"])
    if error:
        logger.info("Coupon %s rejected at order-time: %s", coupon_code, error)
        return None

    return coupon


def _check_cart_items(cart_items):
   
    if not cart_items:
        raise ValueError("Your cart is empty.")
    for item in cart_items:
        if not item.variant.is_active or not item.variant.product.is_active:
            raise ValueError(
                f'"{item.variant.product.name}" is no longer available. '
                "Please remove it from your cart."
            )
        if item.variant.stock < item.quantity:
            available = item.variant.stock
            raise ValueError(
                f'Only {available} unit{"s" if available != 1 else ""} of '
                f'"{item.variant.product.name}" are available.'
            )


def _deduct_wallet(user, wallet_deduction: Decimal, order: Order):
    
    from wallet.models import Wallet

    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.balance < wallet_deduction:
        raise ValueError(
            "Your wallet balance changed. Please refresh and try again."
        )
    wallet.debit(
        amount=wallet_deduction,
        reason=f"Payment for order {order.order_number}",
        order=order,
    )


def _record_coupon_usage(coupon, user, order):
    from coupons.models import CouponUsage

    CouponUsage.objects.create(coupon=coupon, user=user, order=order)


def _create_order_with_retry(defaults: dict) -> Order:
    
    for _ in range(5):
        try:
            return Order.objects.create(**defaults)
        except IntegrityError:
            continue
    raise ValueError(
        "Could not generate a unique order number. Please try again."
    )


def _recalculate_order_total(order: Order) -> None:
    
    active_items = list(order.items.filter(item_status="active"))
    new_subtotal = sum(_d(item.subtotal) for item in active_items)

    new_offer_discount = sum(
        (_d(item.original_price) - _d(item.unit_price)) * item.quantity
        for item in active_items
    )

    
    new_coupon_discount = Decimal("0.00")
    if order.coupon_discount and order.subtotal > 0:
        proportion = new_subtotal / _d(order.subtotal)
        new_coupon_discount = (_d(order.coupon_discount) * proportion).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

    new_total = max(
        Decimal("0.00"),
        new_subtotal - new_coupon_discount + _d(order.shipping_charge),
    )

    order.subtotal = new_subtotal
    order.discount_amount = new_offer_discount + new_coupon_discount
    order.coupon_discount = new_coupon_discount
    order.total_amount = new_total
    order.save(
        update_fields=[
            "subtotal",
            "discount_amount",
            "coupon_discount",
            "total_amount",
            "updated_at",
        ]
    )


def _calculate_item_wallet_refund(order_item: OrderItem, order: Order) -> Decimal:
    
    if not order.wallet_amount or order.wallet_amount <= 0:
        return Decimal("0.00")
    if not order.subtotal or order.subtotal <= 0:
        return Decimal("0.00")

    proportion = _d(order_item.subtotal) / _d(order.subtotal)
    refund = (_d(order.wallet_amount) * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    
    return min(refund, _d(order.wallet_amount))


# PLACE COD ORDER


def place_cod_order(user, cart, address, use_wallet=False, coupon_code=None) -> Order:
    
    cart_items = list(
        cart.items.select_related(
            "variant__product__category",
            "variant__device_model",
        ).prefetch_related("variant__images")
    )

    _check_cart_items(cart_items)

    coupon = _resolve_coupon(coupon_code, user, cart_items)
    totals = _calculate_totals(cart_items, coupon=coupon)
    address_data = _snapshot_address(address)
    total_amount = totals["total_amount"]

    # Wallet split.
    wallet_deduction = Decimal("0.00")
    paid_via_cod = total_amount

    if use_wallet and user:
        from wallet.models import Wallet

        wallet_obj, _ = Wallet.objects.get_or_create(user=user)
        if wallet_obj.balance > 0:
            wallet_deduction = min(_d(wallet_obj.balance), total_amount)
            paid_via_cod = total_amount - wallet_deduction


           
    if wallet_deduction >= total_amount:
        payment_method = "wallet"
    elif wallet_deduction > 0:
        payment_method = "wallet_cod"
    else:
        payment_method = "cod"

    with transaction.atomic():
        order = _create_order_with_retry(
            {
                "user": user,
                "payment_method": payment_method,
                "status": "pending",
                "wallet_amount": wallet_deduction,
                "paid_amount": paid_via_cod,
                "coupon_code": totals["coupon_code"],
                "coupon_discount": totals["coupon_discount"],
                **address_data,
                **{
                    k: v
                    for k, v in totals.items()
                    if k not in ("coupon_code", "coupon_discount")
                },
            }
        )

        
        for cart_item in cart_items:
            OrderItem.objects.create(order=order, **_snapshot_item(cart_item))

        
        for cart_item in cart_items:
            if cart_item.variant.stock < cart_item.quantity:
                raise ValueError(
                    f'Stock for "{cart_item.variant.product.name}" just ran out. '
                    "Please refresh your cart."
                )
            cart_item.variant.stock -= cart_item.quantity
            cart_item.variant.save(update_fields=["stock"])

       
        if wallet_deduction > 0:
            _deduct_wallet(user, wallet_deduction, order)

        # Coupon usage.
        if coupon:
            _record_coupon_usage(coupon, user, order)

            # Referral reward — credit referrer if this is referred user's first order
        try:
            from referrals.services import reward_referrer_on_first_order
            reward_referrer_on_first_order(order)
        except Exception:
            logger.exception("Referral reward failed for order %s", order.order_number)

        # Activity log.
        notes = ["Order placed via Cash on Delivery."]
        if coupon:
            notes.append(
                f"Coupon {coupon.code} applied — ₹{totals['coupon_discount']} off."
            )
        if wallet_deduction > 0:
            notes.append(
                f"₹{wallet_deduction} from wallet; ₹{paid_via_cod} via COD."
            )

        OrderStatusLog.objects.create(
            order=order,
            changed_by=user,
            old_status="",
            new_status="pending",
            note=" ".join(notes),
        )

        # Clear the cart last, after everything else succeeded.
        cart.items.all().delete()

    return order


def cancel_order(order: Order, cancelled_by, reason: str = "") -> Order:
    if "cancelled" not in VALID_TRANSITIONS.get(order.status, []):
        raise ValueError(
            f"This order cannot be cancelled at its current stage "
            f"({order.get_status_display()})."
        )

    with transaction.atomic():
        old_status = order.status
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])

        # Cancel all active items and restore stock
        active_items = list(order.items.filter(item_status="active"))
        for item in active_items:
            item.item_status = "cancelled"
            item.cancellation_reason = reason
            item.save(update_fields=["item_status", "cancellation_reason"])
            if item.variant_id:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=["stock"])

        # Refund to wallet
        wallet_refund_note = ""
        if order.user:
            refund_to_wallet = Decimal("0.00")

            if order.wallet_amount and order.wallet_amount > 0:
                refund_to_wallet += _d(order.wallet_amount)

            if order.payment_method in ("razorpay", "wallet_razorpay") and order.paid_amount > 0:
                refund_to_wallet += _d(order.paid_amount)

            if refund_to_wallet > 0:
                from wallet.models import Wallet
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                wallet.credit(
                    amount=refund_to_wallet,
                    reason=f"Refund for cancelled order {order.order_number}",
                    order=order,
                )
                wallet_refund_note = f" ₹{refund_to_wallet} refunded to wallet."

            # Free up coupon so user can use it again
            if order.coupon_code:
                from django.db.models import F
                from coupons.models import CouponUsage, Coupon
                from django.db.models import F
                CouponUsage.objects.filter(order=order).delete()
                Coupon.objects.filter(code=order.coupon_code).update(
                    times_used=F('times_used') - 1
                )

        OrderStatusLog.objects.create(
            order=order,
            changed_by=cancelled_by,
            old_status=old_status,
            new_status="cancelled",
            note=(reason or "Order cancelled.") + wallet_refund_note,
        )

    return order


def cancel_order_item(order_item: OrderItem, cancelled_by, reason: str = "") -> OrderItem:
    if not order_item.is_cancellable:
        raise ValueError(
            "This item cannot be cancelled. It may already be cancelled, "
            "or the order is no longer in a pending state."
        )

    with transaction.atomic():
        order = order_item.order

        item_subtotal = _d(order_item.subtotal)
        order_subtotal = _d(order.subtotal)

        order_item.item_status = "cancelled"
        order_item.cancellation_reason = reason
        order_item.save(update_fields=["item_status", "cancellation_reason"])

        if order_item.variant_id:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=["stock"])

        _recalculate_order_total(order)

        wallet_refund_note = ""
        if order.user and order_subtotal > 0:
            proportion = item_subtotal / order_subtotal
            total_item_refund = Decimal("0.00")

            if order.wallet_amount and order.wallet_amount > 0:
                wallet_share = (_d(order.wallet_amount) * proportion).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                total_item_refund += wallet_share

            if order.payment_method in ("razorpay", "wallet_razorpay") and order.paid_amount > 0:
                razorpay_share = (_d(order.paid_amount) * proportion).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                total_item_refund += razorpay_share

            if total_item_refund > 0:
                from wallet.models import Wallet
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                wallet.credit(
                    amount=total_item_refund,
                    reason=(
                        f"Partial refund — {order_item.product_name} ×"
                        f" {order_item.quantity} cancelled "
                        f"(Order {order.order_number})"
                    ),
                    order=order,
                )
                order.wallet_amount = max(
                    Decimal("0.00"),
                    _d(order.wallet_amount) - total_item_refund
                )
                order.save(update_fields=["wallet_amount", "updated_at"])
                wallet_refund_note = f" ₹{total_item_refund} refunded to wallet."

        # Auto-close order if no active items remain
        status_note = ""
        remaining_active = order.items.filter(item_status="active").count()
        if remaining_active == 0 and order.status == "pending":
            order.status = "cancelled"
            order.save(update_fields=["status", "updated_at"])
            status_note = " Order automatically closed (no active items remain)."

            # Free up coupon
            if order.coupon_code:
                from django.db.models import F
                from coupons.models import CouponUsage, Coupon
                CouponUsage.objects.filter(order=order).delete()
                Coupon.objects.filter(code=order.coupon_code).update(
                    times_used=F('times_used') - 1
                )

        OrderStatusLog.objects.create(
            order=order,
            changed_by=cancelled_by,
            old_status=order.status,
            new_status=order.status,
            note=(
                f'Item "{order_item.product_name}" cancelled. '
                f"Reason: {reason or 'Not provided'}."
                f"{wallet_refund_note}{status_note}"
            ),
        )

    return order_item


# REQUEST RETURN


def return_order_item(order_item: OrderItem, returned_by, reason: str) -> OrderItem:
    
    if not reason or not reason.strip():
        raise ValueError("A reason is required to submit a return request.")
    if not order_item.is_returnable:
        raise ValueError(
            "This item cannot be returned. It must be in an active state "
            "and the order must be delivered."
        )

    with transaction.atomic():
        order_item.item_status = "return_requested"
        order_item.return_reason = reason.strip()
        order_item.save(update_fields=["item_status", "return_reason"])

        OrderStatusLog.objects.create(
            order=order_item.order,
            changed_by=returned_by,
            old_status=order_item.order.status,
            new_status=order_item.order.status,
            note=(
                f'Return requested for "{order_item.product_name}". '
                f"Reason: {reason.strip()}"
            ),
        )

    return order_item



# APPROVE RETURN (admin action)


def approve_return(order_item: OrderItem, approved_by) -> OrderItem:
    if order_item.item_status != "return_requested":
        raise ValueError("This item does not have a pending return request.")

    with db_transaction.atomic():
        order = order_item.order

        # Capture BEFORE any changes
        item_subtotal  = _d(order_item.subtotal)
        order_subtotal = _d(order.subtotal)
        order_wallet   = _d(order.wallet_amount) if order.wallet_amount else Decimal("0.00")
        order_paid     = _d(order.paid_amount) if order.paid_amount else Decimal("0.00")

        item_wallet_refund = _calculate_item_wallet_refund(order_item, order)

        order_item.item_status = "returned"
        order_item.save(update_fields=["item_status"])

        if order_item.variant_id:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=["stock"])

        # Recalculate AFTER capturing values
        _recalculate_order_total(order)

        refund_amount = Decimal("0.00")

        if order.user and order_subtotal > 0:
            from wallet.models import Wallet
            proportion = item_subtotal / order_subtotal

            if order_wallet > 0:
                wallet_share = (order_wallet * proportion).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                refund_amount += wallet_share

            if order.payment_method in ("razorpay", "wallet_razorpay") and order_paid > 0:
                razorpay_share = (order_paid * proportion).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                refund_amount += razorpay_share

            if order.coupon_discount and order.coupon_discount > 0:
                coupon_share = (_d(order.coupon_discount) * proportion).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                refund_amount = max(Decimal("0.00"), refund_amount - coupon_share)

            if refund_amount > 0:
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                wallet.credit(
                    amount=refund_amount,
                    reason=(
                        f"Refund for returned item: {order_item.product_name} ×"
                        f" {order_item.quantity} (Order {order.order_number})"
                    ),
                    order=order,
                )
                order.wallet_amount = max(
                    Decimal("0.00"),
                    order_wallet - item_wallet_refund,
                )
                order.paid_amount = max(
                    Decimal("0.00"),
                    order_paid - refund_amount,
                )
                order.save(update_fields=["wallet_amount", "paid_amount", "updated_at"])

        OrderStatusLog.objects.create(
            order=order,
            changed_by=approved_by,
            old_status=order.status,
            new_status=order.status,
            note=(
                f'Return approved for "{order_item.product_name}". '
                f"Stock restored. ₹{refund_amount} refunded to wallet."
            ),
        )

    return order_item

# REJECT RETURN 


def reject_return(order_item: OrderItem, rejected_by, reason: str = "") -> OrderItem:
    if order_item.item_status != "return_requested":
        raise ValueError("This item does not have a pending return request.")

    with transaction.atomic():
        order_item.item_status = "return_rejected"
        order_item.return_rejected_reason = reason.strip()
        order_item.save(update_fields=["item_status", "return_rejected_reason"])

        OrderStatusLog.objects.create(
            order=order_item.order,
            changed_by=rejected_by,
            old_status=order_item.order.status,
            new_status=order_item.order.status,
            note=(
                f'Return rejected for "{order_item.product_name}". '
                f"Reason: {reason or 'Not provided'}"
            ),
        )

    return order_item



# ADMIN: CHANGE ORDER STATUS


def change_order_status(order: Order, new_status: str, changed_by, note: str = "") -> Order:
    allowed = VALID_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        current_label = order.get_status_display()
        new_label = dict(Order._meta.get_field("status").choices).get(
            new_status, new_status
        )
        raise ValueError(
            f'Cannot transition from "{current_label}" to "{new_label}".'
        )

   
    if new_status == "cancelled":
        return cancel_order(
            order=order,
            cancelled_by=changed_by,
            reason=note or "Cancelled by admin.",
        )

    with transaction.atomic():
        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        OrderStatusLog.objects.create(
            order=order,
            changed_by=changed_by,
            old_status=old_status,
            new_status=new_status,
            note=note or f"Status updated to {order.get_status_display()}.",
        )

    return order

# RAZORPAY: CREATE ORDER (pre-payment)


def place_razorpay_order(user, cart, address, use_wallet=False, coupon_code=None):
   
    import razorpay
    from django.conf import settings

    cart_items = list(
        cart.items.select_related(
            "variant__product__category",
            "variant__device_model",
        ).prefetch_related("variant__images")
    )

    _check_cart_items(cart_items)

    coupon = _resolve_coupon(coupon_code, user, cart_items)
    totals = _calculate_totals(cart_items, coupon=coupon)
    total_amount = totals["total_amount"]

    # Wallet split.
    wallet_deduction = Decimal("0.00")
    razorpay_amount = total_amount

    if use_wallet and user:
        from wallet.models import Wallet

        wallet_obj, _ = Wallet.objects.get_or_create(user=user)
        if wallet_obj.balance > 0:
            wallet_deduction = min(_d(wallet_obj.balance), total_amount)
            razorpay_amount = total_amount - wallet_deduction

    # Wallet covers everything → fall back to COD flow (no gateway needed).
    if razorpay_amount <= Decimal("0.00"):
        order = place_cod_order(
            user=user,
            cart=cart,
            address=address,
            use_wallet=True,
            coupon_code=coupon_code,
        )
        return order, None

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    razorpay_order = client.order.create(
        {
            "amount": int(razorpay_amount * 100),  # paise
            "currency": "INR",
            "payment_capture": 1,
        }
    )

    return None, {
        "razorpay_order": razorpay_order,
        "totals": totals,
        "wallet_deduction": str(wallet_deduction),
        "razorpay_amount": str(razorpay_amount),
    }


# RAZORPAY: VERIFY PAYMENT & CREATE ORDER


def verify_razorpay_payment(
    user,
    cart,
    address,
    session_data: dict,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
) -> Order:
   
    import razorpay
    from django.conf import settings

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    #  Step 1: Verify signature
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError:
        logger.warning(
            "verify_razorpay_payment: signature failed for payment_id=%s",
            razorpay_payment_id,
        )
        raise ValueError(
            "Payment verification failed. No amount has been deducted. "
            "Please try again."
        )

    #  Step 2: Idempotency 
    existing = Order.objects.filter(
        razorpay_payment_id=razorpay_payment_id
    ).first()
    if existing:
        logger.info(
            "verify_razorpay_payment: duplicate callback for payment_id=%s → "
            "returning existing order %s",
            razorpay_payment_id,
            existing.order_number,
        )
        return existing

    # Step 3: Create order 
    razorpay_amount = _d(session_data.get("razorpay_amount", "0"))
    wallet_deduction = _d(session_data.get("wallet_deduction", "0"))
    coupon_code = session_data.get("coupon_code")

    try:
        cart_items = list(
            cart.items.select_related(
                "variant__product__category",
                "variant__device_model",
            ).prefetch_related("variant__images")
        ) if cart else []

        _check_cart_items(cart_items)

        coupon = _resolve_coupon(coupon_code, user, cart_items)
        totals = _calculate_totals(cart_items, coupon=coupon)
        address_data = _snapshot_address(address)

        with transaction.atomic():
            order = _create_order_with_retry(
                {
                    "user": user,
                    "payment_method": "wallet_razorpay" if wallet_deduction > 0 else "razorpay",
                    "status": "pending",
                    "wallet_amount": wallet_deduction,
                    "paid_amount": razorpay_amount,
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "coupon_code": totals["coupon_code"],
                    "coupon_discount": totals["coupon_discount"],
                    **address_data,
                    **{
                        k: v
                        for k, v in totals.items()
                        if k not in ("coupon_code", "coupon_discount")
                    },
                }
            )

            for cart_item in cart_items:
                OrderItem.objects.create(order=order, **_snapshot_item(cart_item))

            for cart_item in cart_items:
                if cart_item.variant.stock < cart_item.quantity:
                    raise ValueError(
                        f'Stock for "{cart_item.variant.product.name}" just ran out.'
                    )
                cart_item.variant.stock -= cart_item.quantity
                cart_item.variant.save(update_fields=["stock"])

            if wallet_deduction > 0:
                _deduct_wallet(user, wallet_deduction, order)

            if coupon:
                _record_coupon_usage(coupon, user, order)

            # Referral reward — inside transaction so it rolls back if order fails
            try:
                from referrals.services import reward_referrer_on_first_order
                reward_referrer_on_first_order(order)
            except Exception:
                logger.exception("Referral reward failed for order %s", order.order_number)

            notes = ["Order confirmed. Payment received via Razorpay."]
            if wallet_deduction > 0:
                notes.append(
                    f"₹{wallet_deduction} from wallet + ₹{razorpay_amount} via Razorpay."
                )
            if coupon:
                notes.append(
                    f"Coupon {coupon.code} applied — ₹{totals['coupon_discount']} off."
                )

            OrderStatusLog.objects.create(
                order=order,
                changed_by=user,
                old_status="",
                new_status="pending",
                note=" ".join(notes),
            )

            cart.items.all().delete()

        return order

    except Exception as exc:
        # Step 4: Auto-refund on failure 
        logger.error(
            "verify_razorpay_payment: order creation failed after capture. "
            "payment_id=%s user=%s error=%s",
            razorpay_payment_id,
            user.pk,
            exc,
            exc_info=True,
        )
        try:
            client.payment.refund(
                razorpay_payment_id,
                {"amount": int(razorpay_amount * 100)},
            )
            logger.info(
                "verify_razorpay_payment: refund issued for payment_id=%s",
                razorpay_payment_id,
            )
        except Exception as refund_exc:
            logger.critical(
                "verify_razorpay_payment: REFUND FAILED for payment_id=%s error=%s",
                razorpay_payment_id,
                refund_exc,
                exc_info=True,
            )

        raise ValueError(
            "We could not complete your order after payment was received. "
            "A full refund has been initiated and will reflect within "
            "5-7 business days. If you have questions, contact support."
        )