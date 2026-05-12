# services.py is where we put the actual BUSINESS LOGIC.
# Think of it like this:
# - views.py = doorman (receives the request, sends the response)
# - services.py = kitchen (does the actual work)
# This separation means if we add Razorpay later, we just add a new
# function here. The view stays clean and simple.

from django.db import transaction
# transaction.atomic() means "do all of this together or not at all".
# Example: if saving the order succeeds but clearing the cart fails,
# transaction.atomic() rolls EVERYTHING back. No half-saved orders.

from .models import Order, OrderItem, OrderStatusLog
# Our three order models from models.py.

from store.models import CartItem
# We need CartItem to read what's in the user's cart
# and then clear it after the order is placed.


# ── HELPER: SNAPSHOT ADDRESS ─────────────────────────────────────────────────

def _snapshot_address(address):
    # Takes an Address object and returns a plain dictionary.
    # We call this when placing an order to copy the address fields.
    # Why a separate function? Because we use this same logic in one place
    # and it keeps place_cod_order() clean and readable.
    return {
        'shipping_full_name':     address.full_name,
        'shipping_phone':         address.phone,
        'shipping_address_line_1': address.address_line_1,
        'shipping_address_line_2': address.address_line_2 or '',
        'shipping_city':          address.city,
        'shipping_state':         address.state,
        'shipping_postal_code':   address.postal_code,
        'shipping_country':       address.country,
    }


# ── HELPER: SNAPSHOT CART ITEM ────────────────────────────────────────────────

def _snapshot_item(cart_item):
    # Takes a CartItem and returns a dictionary of everything we want
    # to save into OrderItem.
    # We snapshot here so even if the product is edited or deleted later,
    # the order always remembers exactly what was bought.
    variant = cart_item.variant
    product = variant.product

    return {
        'variant':       variant,
        'product_name':  product.name,
        'variant_sku':   variant.sku or '',
        'device_model':  variant.device_model.name if variant.device_model else '',
        'case_type':     variant.get_case_type_display() if variant.case_type else '',
        'color':         variant.get_color_display(),
        'color_code':    variant.color_code,
        'unit_price':    variant.discounted_price,
        # discounted_price already handles discount calculation.
        # We save THIS price, not the original price, because this is
        # what the customer actually paid.
        'quantity':      cart_item.quantity,
        'subtotal':      variant.discounted_price * cart_item.quantity,
        'custom_text':   cart_item.custom_text or '',
        'custom_image':  cart_item.custom_image or None,
    }


# ── HELPER: CALCULATE TOTALS ─────────────────────────────────────────────────

def _calculate_totals(cart_items):
    # Loops through all cart items and calculates:
    # subtotal = sum of all items at their discounted price
    # discount_amount = how much was saved in total
    # shipping_charge = 0 for now (free shipping), easy to change later
    # total_amount = what the customer actually pays

    subtotal        = sum(i.variant.discounted_price * i.quantity for i in cart_items)
    original_total  = sum(i.variant.price * i.quantity for i in cart_items)
    discount_amount = original_total - subtotal
    # discount_amount shows "You saved ₹X" on the invoice.
    # It's the difference between original price and discounted price.

    shipping_charge = 0
    # Free shipping for now. To add shipping logic later,
    # just change this one line — e.g. shipping_charge = 50 if subtotal < 500 else 0

    total_amount = subtotal + shipping_charge
    # Final amount the customer pays.

    return {
        'subtotal':        subtotal,
        'discount_amount': discount_amount,
        'shipping_charge': shipping_charge,
        'total_amount':    total_amount,
    }


# ── MAIN FUNCTION: PLACE COD ORDER ───────────────────────────────────────────

def place_cod_order(user, cart, address):
    # This is the main function that creates the order.
    # It takes:
    #   user    = the logged-in user placing the order
    #   cart    = their Cart object
    #   address = the Address object they selected on checkout
    #
    # It returns the created Order object on success.
    # It raises a ValueError with a message if something goes wrong.
    # The view catches that ValueError and shows the error to the user.

    # Step 1: Get all cart items with related data loaded in one DB query.
    cart_items = list(
        cart.items.select_related(
            'variant__product__category',
            'variant__device_model',
        ).prefetch_related('variant__images')
    )
    # We call list() to evaluate the queryset NOW, before the transaction.
    # select_related loads variant, product, category, device_model in one query
    # instead of hitting the DB separately for each item — much faster.

    # Step 2: Basic validation before touching the database.
    if not cart_items:
        raise ValueError("Your cart is empty.")
    # If someone somehow reaches checkout with an empty cart, stop here.

    # Step 3: Check stock for every item before placing the order.
    for item in cart_items:
        if not item.variant.is_active or not item.variant.product.is_active:
            raise ValueError(
                f'"{item.variant.product.name}" is no longer available.'
            )
        # Product could have been deactivated between adding to cart and checkout.

        if item.variant.stock < item.quantity:
            raise ValueError(
                f'Only {item.variant.stock} units of '
                f'"{item.variant.product.name}" are available.'
            )
        # Stock could have reduced between adding to cart and checkout.
        # We check BEFORE creating anything — don't want a half-created order.

    # Step 4: Calculate all the money amounts.
    totals = _calculate_totals(cart_items)

    # Step 5: Snapshot the address into a plain dictionary.
    address_data = _snapshot_address(address)

    # Step 6: Do everything inside a transaction.
    # If ANY step below fails, the entire thing is rolled back.
    # No orphan orders, no stock deducted without an order being created.
    with transaction.atomic():

        # 6a: Create the Order record.
        order = Order.objects.create(
            user           = user,
            payment_method = 'cod',
            status         = 'pending',
            **address_data,
            # **address_data unpacks the dictionary into keyword arguments.
            # It's the same as writing shipping_full_name=..., shipping_city=... etc.
            # Much cleaner than listing every field manually.
            **totals,
            # Same for totals — unpacks subtotal, discount_amount, etc.
        )

        # 6b: Create one OrderItem for each cart item.
        for cart_item in cart_items:
            item_data = _snapshot_item(cart_item)
            OrderItem.objects.create(
                order = order,
                **item_data,
            )

        # 6c: Deduct stock for each variant.
        for cart_item in cart_items:
            variant = cart_item.variant
            variant.stock -= cart_item.quantity
            # We subtract the ordered quantity from available stock.
            # If stock goes to 0, the product will show as out of stock
            # on the store automatically (because we filter stock__gt=0).
            variant.save(update_fields=['stock'])
            # update_fields=['stock'] tells Django to ONLY update the stock
            # column, not the entire row. Faster and safer — no risk of
            # accidentally overwriting other fields.

        # 6d: Create the first status log entry.
        OrderStatusLog.objects.create(
            order      = order,
            changed_by = user,
            old_status = '',
            # Empty because there's no previous status — this is the first entry.
            new_status = 'pending',
            note       = 'Order placed successfully via Cash on Delivery.',
        )

        # 6e: Clear the cart after successful order placement.
        cart.items.all().delete()
        # Deletes all CartItem rows for this cart.
        # The Cart object itself stays — it'll be reused for next purchase.
        # If we deleted the Cart too, we'd have to recreate it next time.

    # Step 7: Return the created order so the view can redirect to success page.
    return order


# ── CANCEL ENTIRE ORDER ───────────────────────────────────────────────────────

def cancel_order(order, cancelled_by, reason=''):
    # Cancels an entire order.
    # order        = the Order object to cancel
    # cancelled_by = the User doing the cancellation (customer or admin)
    # reason       = optional text explaining why

    # Validate the transition is allowed.
    from .models import VALID_TRANSITIONS
    if 'cancelled' not in VALID_TRANSITIONS.get(order.status, []):
        raise ValueError(
            f"Order cannot be cancelled at this stage ({order.get_status_display()})."
        )
    # Uses our VALID_TRANSITIONS dict from models.py.
    # If order is already shipped, this raises an error — customer can't cancel.

    with transaction.atomic():

        old_status   = order.status
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])

        # Cancel all active items.
        active_items = order.items.filter(item_status='active')
        for item in active_items:
            item.item_status          = 'cancelled'
            item.cancellation_reason  = reason
            item.save(update_fields=['item_status', 'cancellation_reason'])

            # Restore stock for each cancelled item.
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=['stock'])
            # If variant still exists (not deleted), give the stock back.
            # This is what your mentor mentioned — stock must go back up on cancellation.

        # Log the status change.
        OrderStatusLog.objects.create(
            order      = order,
            changed_by = cancelled_by,
            old_status = old_status,
            new_status = 'cancelled',
            note       = reason or 'Order cancelled.',
        )

    return order


# ── CANCEL SINGLE ITEM ────────────────────────────────────────────────────────

def cancel_order_item(order_item, cancelled_by, reason=''):
    # Cancels just ONE item from an order, not the whole order.
    # Example: Order has 2 items, user wants to cancel only 1.

    if not order_item.is_cancellable:
        raise ValueError("This item cannot be cancelled at this stage.")
    # is_cancellable is the property we defined in models.py —
    # item must be active AND order must be pending.

    with transaction.atomic():

        order_item.item_status         = 'cancelled'
        order_item.cancellation_reason = reason
        order_item.save(update_fields=['item_status', 'cancellation_reason'])

        # Restore stock.
        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])

        # Recalculate order totals after item cancellation.
        _recalculate_order_total(order_item.order)
        # When one item is cancelled, the order total must go down.
        # We recalculate and save the new total.

        # Log it.
        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = cancelled_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            # Order status itself doesn't change when cancelling one item.
            # We still log it so admin can see what happened.
            note       = f'Item "{order_item.product_name}" cancelled. Reason: {reason or "Not provided"}',
        )

    return order_item


# ── RETURN SINGLE ITEM ────────────────────────────────────────────────────────

def return_order_item(order_item, returned_by, reason):
    # Returns one item from a delivered order.
    # reason is MANDATORY here — we enforce it in the view too.

    if not reason or not reason.strip():
        raise ValueError("A reason is required to return an item.")
    # Double safety — view will also check this, but we check here too.

    if not order_item.is_returnable:
        raise ValueError("This item cannot be returned at this stage.")

    with transaction.atomic():

        order_item.item_status  = 'returned'
        order_item.return_reason = reason.strip()
        order_item.save(update_fields=['item_status', 'return_reason'])

        # Restore stock when item is returned.
        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])
        # Returned product goes back to inventory — stock increases.

        # Recalculate order total.
        _recalculate_order_total(order_item.order)

        # Log it.
        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = returned_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = f'Item "{order_item.product_name}" returned. Reason: {reason}',
        )

    return order_item


# ── HELPER: RECALCULATE ORDER TOTAL ──────────────────────────────────────────

def _recalculate_order_total(order):
    # After cancelling or returning an item, the order total must be updated.
    # We only count items that are still 'active' — not cancelled or returned.

    active_items = order.items.filter(item_status='active')
    # Gets only the items that are still valid in the order.

    new_subtotal = sum(item.subtotal for item in active_items)
    # Adds up subtotals of only active items.

    new_total = max(0, new_subtotal + order.shipping_charge)
    # Keeps the original shipping and discount, just recalculates the base.
    # We use max(0, ...) below to make sure total never goes negative.
    new_total = max(0, new_total)

    order.subtotal     = new_subtotal
    order.total_amount = new_total
    order.save(update_fields=['subtotal', 'total_amount', 'updated_at'])
    # Only saves these three fields — fast and safe.


# ── ADMIN: CHANGE ORDER STATUS ────────────────────────────────────────────────

def change_order_status(order, new_status, changed_by, note=''):
    # Used by admin to move an order through the status flow.
    # Validates the transition is allowed before saving.

    from .models import VALID_TRANSITIONS
    allowed = VALID_TRANSITIONS.get(order.status, [])

    if new_status not in allowed:
        raise ValueError(
            f'Cannot change status from "{order.get_status_display()}" '
            f'to "{dict(Order._meta.get_field("status").choices).get(new_status, new_status)}".'
        )
    # This is the strict validation you and your mentor discussed.
    # shipped → delivered is NOT in VALID_TRANSITIONS, so this raises an error.
    # Admin must go shipped → out_for_delivery → delivered. No shortcuts.

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