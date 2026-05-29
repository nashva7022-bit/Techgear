

from django.db import transaction,IntegrityError

from .models import Order, OrderItem, OrderStatusLog


from store.models import CartItem

# SNAPSHOT ADDRESS

def _snapshot_address(address):
    
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


#  SNAPSHOT CART ITEM 

def _snapshot_item(cart_item):
    
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
        
        'quantity':      cart_item.quantity,
        'subtotal':      variant.discounted_price * cart_item.quantity,
        'custom_text':   cart_item.custom_text or '',
        'custom_image':  cart_item.custom_image or None,
    }


#  CALCULATE TOTALS

def _calculate_totals(cart_items):
    

    subtotal        = sum(i.variant.discounted_price * i.quantity for i in cart_items)
    original_total  = sum(i.variant.price * i.quantity for i in cart_items)
    discount_amount = original_total - subtotal
    
    shipping_charge = 0
    
    total_amount = subtotal + shipping_charge


    return {
        'subtotal':        subtotal,
        'discount_amount': discount_amount,
        'shipping_charge': shipping_charge,
        'total_amount':    total_amount,
    }


# PLACE COD ORDER 

def place_cod_order(user, cart, address):
   
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
            raise ValueError(
                f'"{item.variant.product.name}" is no longer available.'
            )
        
        if item.variant.stock < item.quantity:
            raise ValueError(
                f'Only {item.variant.stock} units of '
                f'"{item.variant.product.name}" are available.'
            )
        
    totals = _calculate_totals(cart_items)

    
    address_data = _snapshot_address(address)

   
    with transaction.atomic():

        #Create the Order record.
        order = None
        for _ in range(5):
            try:
                order = Order.objects.create(
                    user           = user,
                payment_method = 'cod',
                status         = 'pending',
                **address_data,
                **totals,
            )
                break
            except IntegrityError:
                continue

        if not order:
            raise ValueError("Could not generate a unique order number. Please try again.")

        #  Create one OrderItem for each cart item.
        for cart_item in cart_items:
            item_data = _snapshot_item(cart_item)
            OrderItem.objects.create(
                order = order,
                **item_data,
            )

        #  Deduct stock for each variant.
        for cart_item in cart_items:
            variant = cart_item.variant
            variant.stock -= cart_item.quantity
           
            variant.save(update_fields=['stock'])
            
        
        OrderStatusLog.objects.create(
            order      = order,
            changed_by = user,
            old_status = '',
            
            new_status = 'pending',
            note       = 'Order placed successfully via Cash on Delivery.',
        )

        # 6e: Clear the cart after successful order placement.
        cart.items.all().delete()
       
    return order


#  CANCEL ENTIRE ORDER

def cancel_order(order, cancelled_by, reason=''):
   
    from .models import VALID_TRANSITIONS
    if 'cancelled' not in VALID_TRANSITIONS.get(order.status, []):
        raise ValueError(
            f"Order cannot be cancelled at this stage ({order.get_status_display()})."
        )
    
    with transaction.atomic():
        old_status = order.status 

        
        order.status        = 'cancelled'
        order.subtotal      = 0
        order.discount_amount = 0
        order.total_amount  = 0
        order.save(update_fields=['status', 'subtotal', 'discount_amount', 'total_amount', 'updated_at'])
        
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
           
       
        OrderStatusLog.objects.create(
            order      = order,
            changed_by = cancelled_by,
            old_status = old_status,       
            new_status = 'cancelled',     
            note       = reason or 'Order cancelled.',
        )

    return order


# CANCEL SINGLE ITEM 

def cancel_order_item(order_item, cancelled_by, reason=''):
   
    if not order_item.is_cancellable:
        raise ValueError("This item cannot be cancelled at this stage.")
   
    with transaction.atomic():

        order_item.item_status         = 'cancelled'
        order_item.cancellation_reason = reason
        order_item.save(update_fields=['item_status', 'cancellation_reason'])

        # Restore stock.
        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])

    
        _recalculate_order_total(order_item.order)
        
        # Log it.
        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = cancelled_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
           
            note       = f'Item "{order_item.product_name}" cancelled. Reason: {reason or "Not provided"}',
        )

    return order_item


#  RETURN SINGLE ITEM 

def return_order_item(order_item, returned_by, reason):
    if not reason or not reason.strip():
        raise ValueError("A reason is required to return an item.")

    if not order_item.is_returnable:
        raise ValueError("This item cannot be returned at this stage.")

    with transaction.atomic():
        # Don't restore stock yet — wait for admin approval
        order_item.item_status   = 'return_requested' 
        order_item.return_reason = reason.strip()
        order_item.save(update_fields=['item_status', 'return_reason'])

        # Log the request
        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = returned_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = f'Return requested for "{order_item.product_name}". Reason: {reason}',
        )

    return order_item



def approve_return(order_item, approved_by):
    if order_item.item_status != 'return_requested':
        raise ValueError("This item does not have a pending return request.")

    with transaction.atomic():
        order_item.item_status = 'returned'
        order_item.save(update_fields=['item_status'])

        # NOW restore stock — item is physically back
        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=['stock'])

        _recalculate_order_total(order_item.order)

        OrderStatusLog.objects.create(
            order      = order_item.order,
            changed_by = approved_by,
            old_status = order_item.order.status,
            new_status = order_item.order.status,
            note       = f'Return approved for "{order_item.product_name}". Stock restored.',
        )

    return order_item


def reject_return(order_item, rejected_by, reason=''):
    if order_item.item_status != 'return_requested':
        raise ValueError("This item does not have a pending return request.")

    with transaction.atomic():
        # Set to return_rejected — permanently blocks re-requesting
        order_item.item_status          = 'return_rejected'
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


# HELPER: RECALCULATE ORDER TOTAL 

def _recalculate_order_total(order):
    active_items = list(order.items.filter(item_status='active'))
    new_subtotal = sum(item.subtotal for item in active_items)
    new_total    = max(0, new_subtotal + order.shipping_charge)

    order.subtotal        = new_subtotal
    order.total_amount    = new_total
    
    order.save(update_fields=['subtotal', 'total_amount', 'updated_at'])
    
#  ADMIN: CHANGE ORDER STATUS 

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