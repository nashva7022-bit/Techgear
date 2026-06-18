from django.db import transaction, IntegrityError
from django.db import transaction as db_transaction

from .models import Order, OrderItem, OrderStatusLog
from store.models import CartItem
from decimal import Decimal, ROUND_DOWN
from .models import VALID_TRANSITIONS
from offers.utils import get_effective_price


# ── SNAPSHOT ADDRESS ──────────────────────────────────────────────────────────

def _snapshot_address(address):
    return {
        'shipping_full_name':      address.full_name,
        'shipping_phone':           address.phone,
        'shipping_address_line_1': address.address_line_1,
        'shipping_address_line_2': address.address_line_2 or '',
        'shipping_city':           address.city,
        'shipping_state':          address.state,
        'shipping_postal_code':    address.postal_code,
        'shipping_country':        address.country,
    }


# ── SNAPSHOT CART ITEM (FIXED) ────────────────────────────────────────────────

def _snapshot_item(cart_item):
    variant = cart_item.variant
    product = variant.product
    
    # 1. Fetch the real promotional offer price dynamically
    effective_price, _ = get_effective_price(variant)
    
    # 2. Recalculate item subtotal based on promotional value + customization
    discounted_subtotal = (effective_price * cart_item.quantity) + cart_item.customization_charge
    
    return {
        'variant':              variant,
        'product_name':         product.name,
        'variant_sku':          variant.sku or '',
        'device_model':         variant.device_model.name if variant.device_model else '',
        'case_type':            variant.get_case_type_display() if variant.case_type else '',
        'color':                variant.get_color_display(),
        'color_code':           variant.color_code,
        'original_price':       variant.price,     # MRP per unit, before any offer
        'unit_price':           effective_price,   # Sale price per unit
        'quantity':             cart_item.quantity,
        'subtotal':             discounted_subtotal,  # Correctly scaled subtotal
        'custom_text':          cart_item.custom_text or '',
        'custom_image':         cart_item.custom_image or None,
        'customization_charge': cart_item.customization_charge,
    }
# ── CALCULATE TOTALS (FIXED) ──────────────────────────────────────────────────

def _calculate_totals(cart_items):
    discounted_subtotal  = Decimal('0.00')   # sum of item.subtotal (offer price + customization)
    total_offer_discount = Decimal('0.00')   # for "you saved ₹X" display only

    for item in cart_items:
        eff_price, _ = get_effective_price(item.variant)
        item_regular_total     = item.variant.price * item.quantity
        item_discounted_total  = (eff_price * item.quantity) + item.customization_charge

        discounted_subtotal  += item_discounted_total
        total_offer_discount += (item_regular_total - (eff_price * item.quantity))

    shipping_charge = Decimal('0.00')
    total_amount     = discounted_subtotal + shipping_charge

    return {
        'subtotal':        discounted_subtotal,   # matches sum(item.subtotal) — discounted, includes customization
        'discount_amount': total_offer_discount,  # display-only: total saved from offers
        'shipping_charge': shipping_charge,
        'total_amount':    total_amount,
    
    }


# ── PLACE COD ORDER ───────────────────────────────────────────────────────────

def place_cod_order(user, cart, address, use_wallet=False):
    cart_items = list(
        cart.items.select_related(
            'variant__product__category',
            'variant__device_model',
        ).prefetch_related('variant__images')
    )

    if not cart_items:
        raise ValueError("Your cart is empty.")

    for item in cart_items:
        if not item.variant.is_active or not item.variant.product.is_active:
            raise ValueError(f'"{item.variant.product.name}" is no longer available.')
        if item.variant.stock < item.quantity:
            raise ValueError(
                f'Only {item.variant.stock} units of '
                f'"{item.variant.product.name}" are available.'
            )

    totals       = _calculate_totals(cart_items)
    address_data = _snapshot_address(address)
    total_amount = totals['total_amount']

    # Wallet split
    wallet_deduction = Decimal('0.00')
    paid_via_cod     = total_amount

    if use_wallet and user:
        from wallet.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=user)
        if wallet.balance > 0:
            wallet_deduction = min(wallet.balance, total_amount)
            paid_via_cod     = total_amount - wallet_deduction

    with transaction.atomic():
        # Create Order
        order = None
        for _ in range(5):
            try:
                order = Order.objects.create(
                    user           = user,
                    payment_method = 'cod',
                    status         = 'pending',
                    wallet_amount  = wallet_deduction,
                    paid_amount    = paid_via_cod,
                    **address_data,
                    **totals,
                )
                break
            except IntegrityError:
                continue

        if not order:
            raise ValueError("Could not generate a unique order number. Please try again.")

        # Create OrderItems using the fixed snap function
        for cart_item in cart_items:
            OrderItem.objects.create(order=order, **_snapshot_item(cart_item))

        # Deduct stock
        for cart_item in cart_items:
            cart_item.variant.stock -= cart_item.quantity
            cart_item.variant.save(update_fields=['stock'])

        # Debit wallet atomically
        if wallet_deduction > 0:
            from wallet.models import Wallet
            wallet = Wallet.objects.select_for_update().get(user=user)
            if wallet.balance < wallet_deduction:
                raise ValueError("Insufficient wallet balance. Please try again.")
            wallet.debit(
                amount = wallet_deduction,
                reason = f'Payment for order {order.order_number}',
                order  = order,
            )

        # Status log
        wallet_note = (
            f' (₹{wallet_deduction} from wallet, ₹{paid_via_cod} via COD)'
            if wallet_deduction > 0 else ''
        )
        OrderStatusLog.objects.create(
            order      = order,
            changed_by = user,
            old_status = '',
            new_status = 'pending',
            note       = f'Order placed successfully via Cash on Delivery.{wallet_note}',
        )

        # Clear cart
        cart.items.all().delete()

    return order


# ── CANCEL ENTIRE ORDER ───────────────────────────────────────────────────────

def cancel_order(order, cancelled_by, reason=''):
    if 'cancelled' not in VALID_TRANSITIONS.get(order.status, []):
        raise ValueError(
            f"Order cannot be cancelled at this stage ({order.get_status_display()})."
        )

    with transaction.atomic():
        old_status = order.status

        order.status          = 'cancelled'
        order.subtotal        = 0
        order.discount_amount = 0
        order.total_amount    = 0
        order.save(update_fields=['status', 'subtotal', 'discount_amount', 'total_amount', 'updated_at'])

        # Cancel all active items + restore stock
        active_items = order.items.filter(item_status='active')
        for item in active_items:
            item.item_status         = 'cancelled'
            item.cancellation_reason = reason
            item.save(update_fields=['item_status', 'cancellation_reason'])
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=['stock'])

        # Wallet refund
        wallet_refund_note = ''
        if order.wallet_amount > 0 and order.user:
            from wallet.models import Wallet
            wallet, _ = Wallet.objects.get_or_create(user=order.user)
            wallet.credit(
                amount = order.wallet_amount,
                reason = f'Refund for cancelled order {order.order_number}',
                order  = order,
            )
            wallet_refund_note = f' ₹{order.wallet_amount} refunded to wallet.'

        OrderStatusLog.objects.create(
            order      = order,
            changed_by = cancelled_by,
            old_status = old_status,
            new_status = 'cancelled',
            note       = (reason or 'Order cancelled.') + wallet_refund_note,
        )

    return order


# ── CANCEL SINGLE ITEM ────────────────────────────────────────────────────────

def cancel_order_item(order_item, cancelled_by, reason=''):
    if not order_item.is_cancellable:
        raise ValueError("This item cannot be cancelled at this stage.")

    with transaction.atomic():
        order = order_item.order

        item_wallet_refund = _calculate_item_wallet_refund(order_item, order)

        order_item.item_status         = 'cancelled'
        order_item.cancellation_reason = reason
        order_item.save(update_fields=['item_status', 'cancellation_reason'])

        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])

        _recalculate_order_total(order)

        wallet_refund_note = ''
        if item_wallet_refund > 0 and order.user:
            from wallet.models import Wallet
            wallet, _ = Wallet.objects.get_or_create(user=order.user)
            wallet.credit(
                amount = item_wallet_refund,
                reason = (
                    f'Partial refund for cancelled item: '
                    f'{order_item.product_name} × {order_item.quantity} '
                    f'(Order {order.order_number})'
                ),
                order = order,
            )
            order.wallet_amount = max(0, order.wallet_amount - item_wallet_refund)
            order.save(update_fields=['wallet_amount', 'updated_at'])
            wallet_refund_note = f' ₹{item_wallet_refund} refunded to wallet.'

        OrderStatusLog.objects.create(
            order      = order,
            changed_by = cancelled_by,
            old_status = order.status,
            new_status = order.status,
            note       = (
                f'Item "{order_item.product_name}" cancelled. '
                f'Reason: {reason or "Not provided"}.{wallet_refund_note}'
            ),
        )

    return order_item


# ── REQUEST RETURN ────────────────────────────────────────────────────────────

def return_order_item(order_item, returned_by, reason):
    if not reason or not reason.strip():
        raise ValueError("A reason is required to return an item.")
    if not order_item.is_returnable:
        raise ValueError("This item cannot be returned at this stage.")

    with transaction.atomic():
        order_item.item_status   = 'return_requested'
        order_item.return_reason = reason.strip()
        order_item.save(update_fields=['item_status', 'return_reason'])

        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = returned_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = f'Return requested for "{order_item.product_name}". Reason: {reason}',
        )

    return order_item


# ── APPROVE RETURN ────────────────────────────────────────────────────────────

def approve_return(order_item, approved_by):
    if order_item.item_status != 'return_requested':
        raise ValueError("This item does not have a pending return request.")

    with db_transaction.atomic():
        order_item.item_status = 'returned'
        order_item.save(update_fields=['item_status'])

        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])

        _recalculate_order_total(order_item.order)

        if order_item.order.user:
            from wallet.models import Wallet
            wallet, _ = Wallet.objects.get_or_create(user=order_item.order.user)
            wallet.credit(
                amount = order_item.subtotal,
                reason = (
                    f'Refund for returned item: '
                    f'{order_item.product_name} × {order_item.quantity} '
                    f'(Order {order_item.order.order_number})'
                ),
                order = order_item.order,
            )

        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = approved_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = (
                f'Return approved for "{order_item.product_name}". '
                f'Stock restored. ₹{order_item.subtotal} credited to wallet.'
            ),
        )

    return order_item


# ── REJECT RETURN ─────────────────────────────────────────────────────────────

def reject_return(order_item, rejected_by, reason=''):
    if order_item.item_status != 'return_requested':
        raise ValueError("This item does not have a pending return request.")

    with transaction.atomic():
        order_item.item_status            = 'return_rejected'
        order_item.return_rejected_reason = reason.strip()
        order_item.save(update_fields=['item_status', 'return_rejected_reason'])

        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = rejected_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = f'Return rejected for "{order_item.product_name}". Reason: {reason or "Not provided"}',
        )

    return order_item


# ── ADMIN: CHANGE ORDER STATUS ────────────────────────────────────────────────

def change_order_status(order, new_status, changed_by, note=''):
    from .models import VALID_TRANSITIONS
    allowed = VALID_TRANSITIONS.get(order.status, [])

    if new_status not in allowed:
        raise ValueError(
            f'Cannot change status from "{order.get_status_display()}" '
            f'to "{dict(Order._meta.get_field("status").choices).get(new_status, new_status)}".'
        )

    with transaction.atomic():
        old_status   = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        OrderStatusLog.objects.create(
            order      = order,
            changed_by = changed_by,
            old_status = old_status,
            new_status = new_status,
            note       = note or f'Status updated to {order.get_status_display()}.',
        )

    return order


# ── RECALCULATE ORDER TOTAL ──────────────────────────────────────────────────

def _recalculate_order_total(order):
    active_items = list(order.items.filter(item_status='active'))
    new_subtotal = sum(item.subtotal for item in active_items)

    # Recalculate discount from only the still-active items, so it stays accurate
    # after partial cancellation/return — not the frozen original-order discount.
    new_discount = sum(
        (item.original_price - item.unit_price) * item.quantity
        for item in active_items
    )

    new_total = max(0, new_subtotal + order.shipping_charge)

    order.subtotal        = new_subtotal
    order.discount_amount = new_discount
    order.total_amount    = new_total
    order.save(update_fields=['subtotal', 'discount_amount', 'total_amount', 'updated_at'])


# ── CALCULATE ITEM WALLET REFUND ──────────────────────────────────────────────

def _calculate_item_wallet_refund(order_item, order):
    if not order.wallet_amount or order.wallet_amount <= 0:
        return Decimal('0.00')

    original_total = order.subtotal + order_item.subtotal
    if original_total <= 0:
        return Decimal('0.00')

    proportion    = Decimal(str(order_item.subtotal)) / Decimal(str(original_total))
    wallet_refund = (proportion * Decimal(str(order.wallet_amount))).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN
    )
    return wallet_refund