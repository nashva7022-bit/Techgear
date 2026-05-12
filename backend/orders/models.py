
import uuid
# uuid is Python's built-in module for generating unique IDs.
# We use it to create order numbers like ORD-A3F2B1C4.
# Without this, we'd have to use auto-increment integers (1, 2, 3...)
# which are ugly, predictable, and expose how many orders you have.

from django.db import models
# Standard Django import. Without this, we can't define any model fields
# like CharField, ForeignKey, DecimalField etc.
from cloudinary.models import CloudinaryField

from django.conf import settings
# This gives us settings.AUTH_USER_MODEL — the correct way to reference
# your custom User model. If we wrote 'users.User' directly and someone
# renamed the app, everything would break. settings.AUTH_USER_MODEL is safe.

from django.utils import timezone
# Django's timezone-aware datetime. Without this, if your server is in
# a different timezone than your users, timestamps would be wrong.


# ── ORDER STATUS CHOICES ──────────────────────────────────────────────────────

ORDER_STATUS_CHOICES = [
    ('pending',           'Pending'),
    ('shipped',           'Shipped'),
    ('out_for_delivery',  'Out for Delivery'),
    ('delivered',         'Delivered'),
    ('cancelled',         'Cancelled'),
]
# These are the only valid statuses an order can have.
# Stored as a list of tuples: (database_value, human_readable_label).
# 'pending' is what gets saved in DB. 'Pending' is what shows on screen.
# Without this, you'd have free-text status fields — admin could type
# 'Deliverd' (typo) and nothing would catch it.

VALID_TRANSITIONS = {
    'pending':           ['shipped', 'cancelled'],
    'shipped':           ['out_for_delivery'],
    'out_for_delivery':  ['delivered'],
    'delivered':         [],
    'cancelled':         [],
}
# This is the strict status flow your mentor and you discussed.
# pending → shipped → out_for_delivery → delivered
# pending → cancelled (only before shipped)
# delivered and cancelled are terminal — nothing comes after them.
# Without this dict, someone could change status from 'shipped' directly
# to 'delivered', skipping 'out_for_delivery'. We validate against this
# in both admin and user views before saving any status change.


# ── ITEM STATUS CHOICES ───────────────────────────────────────────────────────

ITEM_STATUS_CHOICES = [
    ('active',     'Active'),
    ('cancelled',  'Cancelled'),
    ('returned',   'Returned'),
]
# Each individual item inside an order has its own status.
# This is needed because a user can cancel or return ONE product
# from an order without cancelling the entire order.
# Example: Order has iPhone case + laptop skin. User cancels only the laptop skin.
# Without per-item status, you'd have to cancel the whole order.


# ── PAYMENT METHOD CHOICES ────────────────────────────────────────────────────

PAYMENT_METHOD_CHOICES = [
    ('cod', 'Cash on Delivery'),
    # ('razorpay', 'Razorpay'),  ← add this later when online payment is needed
]
# Only COD for now as discussed. Defined as choices so it's easy to
# add Razorpay later — just uncomment one line and add the function
# in services.py. Without this structure, adding a new payment method
# later would require changes in many places.


# ── HELPER FUNCTION ───────────────────────────────────────────────────────────

def generate_order_number():
    return 'ORD-' + uuid.uuid4().hex[:8].upper()
# This generates order numbers like ORD-A3F2B1C4.
# uuid4() generates a random UUID. .hex gives it as a plain string.
# [:8] takes first 8 characters. .upper() makes it look clean.
# This function is passed to the order_number field as default=
# so every new order automatically gets a unique readable ID.
# Without this, you'd use the database PK (1, 2, 3) which is ugly
# and tells customers/competitors how many orders you have.


# ── ORDER MODEL ───────────────────────────────────────────────────────────────

class Order(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders',
    )
    # Links each order to the user who placed it.
    # on_delete=SET_NULL means if the user account is deleted, the order
    # still exists in the database (important for accounting/records).
    # If we used CASCADE, deleting a user would delete all their orders —
    # terrible for business records and invoices.
    # related_name='orders' means we can do user.orders.all() anywhere.

    order_number = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_number,
        editable=False,
    )
    # Human-readable unique order ID like ORD-A3F2B1C4.
    # unique=True ensures no two orders ever get the same number.
    # default=generate_order_number calls our function automatically on creation.
    # editable=False means it can't be changed after creation — order numbers
    # should be permanent. Without unique=True, two orders could get the same
    # number which would break invoice downloads and order lookups.

    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='pending',
    )
    # Current status of the order. Always starts as 'pending'.
    # choices= restricts what values can be stored — Django will reject
    # anything not in ORDER_STATUS_CHOICES.
    # Without default='pending', you'd have to manually set it every time
    # an order is created.

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cod',
    )
    # How the customer is paying. Only COD right now.
    # Stored so the invoice and order detail can show "Cash on Delivery".
    # When Razorpay is added later, this field needs no changes.

    # ── ADDRESS SNAPSHOT FIELDS ──
    # IMPORTANT: We do NOT store a ForeignKey to the Address model here.
    # We copy the address fields directly into the order at time of placing.
    # Why? Because if the user later edits or deletes that address,
    # the order should still show the address it was ACTUALLY delivered to.
    # Think of it like a receipt — it captures the moment, not a live link.

    shipping_full_name = models.CharField(max_length=100)
    # The name on the address at time of order. Copied from Address.full_name.

    shipping_phone = models.CharField(max_length=15)
    # Phone at time of order. Copied from Address.phone.

    shipping_address_line_1 = models.CharField(max_length=255)
    # House/flat number and street. Copied from Address.address_line_1.

    shipping_address_line_2 = models.CharField(max_length=255, blank=True, default='')
    # Optional second line. blank=True because not everyone fills this.

    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100, default='India')
    # City, state, pincode, country — all copied from Address at order time.

    # ── PRICING FIELDS ──
    # These are also snapshots. Prices can change — a product's price today
    # might be different next month. The order must always show what the
    # customer ACTUALLY paid, not today's price.

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    # Sum of all items (before discount and shipping).
    # max_digits=10 supports up to 99,999,999.99 — enough for any order.
    # decimal_places=2 keeps amounts like 499.00 or 1299.50 accurate.
    # Without DecimalField, floating point errors (0.1 + 0.2 = 0.30000000004)
    # would make your invoice totals wrong — never use FloatField for money.

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Total discount applied across all items. Stored separately so the
    # invoice can show "You saved ₹200". Without this you can't show savings.

    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Shipping fee. Stored separately so it can be shown on invoice.
    # Default 0 because you might offer free shipping sometimes.

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Final amount = subtotal - discount + shipping.
    # Stored explicitly so we never have to recalculate it later.
    # If discount logic changes in future, old orders still show correct total.

    # ── TIMESTAMPS ──

    created_at = models.DateTimeField(default=timezone.now)
    # When the order was placed. default=timezone.now (not auto_now_add)
    # so it can be passed explicitly in tests if needed.
    # This is what shows as "Order Date" in listings and invoices.

    updated_at = models.DateTimeField(auto_now=True)
    # auto_now=True updates this every time the order is saved.
    # Useful for knowing when status was last changed.
    # Without this, you'd have no way to know when an order was last modified.

    class Meta:
        ordering = ['-created_at']
        # Orders list always shows newest first — descending by date.
        # Without this, you'd have to add .order_by('-created_at') in every view.

    def __str__(self):
        return f"{self.order_number} — {self.user.email if self.user else 'Deleted User'}"
    # Human-readable label in Django admin and shell.
    # Handles the case where user was deleted (is None because of SET_NULL).

    @property
    def can_cancel(self):
        return self.status == 'pending'
    # A convenience property used in templates to show/hide the Cancel button.
    # Only pending orders can be cancelled by the user.
    # Without this, you'd write this logic in every template — messy.

    @property
    def can_return(self):
        return self.status == 'delivered'
    # Return is only allowed after delivery. Used in templates same as above.

    @property
    def shipping_address_display(self):
        parts = [
            self.shipping_address_line_1,
            self.shipping_address_line_2,
            self.shipping_city,
            self.shipping_state,
            self.shipping_postal_code,
            self.shipping_country,
        ]
        return ', '.join(p for p in parts if p)
    # Formats the full address as a single string for display in templates
    # and invoices. Skips blank fields (address_line_2 is optional).
    # Without this, every template would need to manually join the fields.


# ── ORDER ITEM MODEL ──────────────────────────────────────────────────────────

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    # Links this item to its parent order.
    # CASCADE means if the order is deleted, all its items are deleted too.
    # That's correct — items have no meaning without their order.
    # related_name='items' lets us do order.items.all() in views and templates.

    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )
    # Link to the actual product variant ordered.
    # SET_NULL means if admin deletes the variant, order item still exists.
    # null=True required when using SET_NULL.
    # We keep this link so we can increment stock on cancellation/return.
    # But we don't rely on it for displaying product info — we use
    # snapshot fields below for that.

    # ── SNAPSHOT FIELDS ──
    # These copy the product/variant details at time of order.
    # If the product name changes or variant is deleted, the order
    # still shows exactly what was purchased.

    product_name = models.CharField(max_length=150)
    # e.g. "Carbon Fibre Phone Case". Copied from variant.product.name.

    variant_sku = models.CharField(max_length=50, blank=True, default='')
    # e.g. "CARBON-F-BLA-1234". Copied from variant.sku.
    # Shown on invoice. blank=True because SKU might be empty.

    device_model = models.CharField(max_length=100, blank=True, default='')
    # e.g. "iPhone 15 Pro". Copied from variant.device_model.name.
    # blank=True because some products might not have a device model.

    case_type = models.CharField(max_length=50, blank=True, default='')
    # e.g. "Slim Fit". Copied from variant.get_case_type_display().
    # blank=True because non-customizable products don't have case types.

    color = models.CharField(max_length=50, blank=True, default='')
    # e.g. "Black". Copied from variant.get_color_display().

    color_code = models.CharField(max_length=7, blank=True, default='')
    # e.g. "#000000". For showing the colour swatch on order detail page.

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Price per unit AT TIME OF ORDER. Copied from variant.discounted_price.
    # Without this snapshot, if price changes tomorrow, old orders would
    # show wrong prices. This is a legal requirement for invoices.

    quantity = models.PositiveIntegerField(default=1)
    # How many units were ordered. Min 1, enforced by PositiveIntegerField.

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    # unit_price × quantity. Stored so invoice calculation is always correct
    # even if unit_price logic changes later.

    # ── CUSTOMIZATION FIELDS ──
    # Carried over from CartItem if the product is customizable.

    custom_text = models.CharField(max_length=100, blank=True, default='')
    # The text the user typed for customization (e.g. name on phone case).
    # blank=True because most products aren't customizable.

   
    custom_image = CloudinaryField('custom_image', blank=True, null=True)
    # The image the user uploaded for customization.
    # null=True because it's optional even for customizable products.

    # ── ITEM STATUS ──

    item_status = models.CharField(
        max_length=20,
        choices=ITEM_STATUS_CHOICES,
        default='active',
    )
    # Per-item status — active, cancelled, or returned.
    # This lets a user cancel one item without cancelling the whole order.
    # Without this, you'd have to cancel the entire order just to cancel one product.

    cancellation_reason = models.TextField(blank=True, default='')
    # Optional reason when user or admin cancels this item.
    # blank=True because reason is optional for cancellation.
    # TextField (not CharField) because reason can be long.

    return_reason = models.TextField(blank=True, default='')
    # Mandatory reason when user returns this item.
    # Still defined as blank=True in DB — we enforce "mandatory" in the view/form,
    # not at DB level, because DB-level required fields cause migration headaches.

    created_at = models.DateTimeField(default=timezone.now)
    # When this item was added to the order. Useful for audit purposes.

    class Meta:
        ordering = ['created_at']
        # Items display in the order they were added — natural reading order.

    def __str__(self):
        return f"{self.product_name} × {self.quantity} (Order: {self.order.order_number})"

    @property
    def is_cancellable(self):
        return (
            self.item_status == 'active' and
            self.order.status == 'pending'
        )
    # Item can only be cancelled if:
    # 1. The item itself is still active (not already cancelled/returned)
    # 2. The order hasn't shipped yet
    # Used in templates to show/hide the Cancel button per item.

    @property
    def is_returnable(self):
        return (
            self.item_status == 'active' and
            self.order.status == 'delivered'
        )
    # Item can only be returned after the order is delivered
    # and if the item hasn't already been cancelled or returned.


# ── ORDER STATUS LOG (ACTIVITY LOG) ──────────────────────────────────────────

class OrderStatusLog(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_logs',
    )
    # Links log entry to its order.
    # CASCADE — if order is deleted, its logs are deleted too. That's fine.

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes',
    )
    # Who made this status change — admin user or the customer themselves.
    # SET_NULL so log entry survives even if the admin account is deleted.
    # blank=True allows system-generated logs with no specific user.

    old_status = models.CharField(max_length=20, blank=True, default='')
    # What the status WAS before the change. blank=True for the very first
    # log entry when order is created (no previous status exists).

    new_status = models.CharField(max_length=20)
    # What the status CHANGED TO. Always required — every log entry must
    # record what it changed to.

    note = models.TextField(blank=True, default='')
    # Optional note explaining the change.
    # e.g. "Shipped via Delhivery, tracking #12345"
    # e.g. "Customer requested cancellation"

    created_at = models.DateTimeField(default=timezone.now)
    # When this status change happened. Used to show a timeline
    # on the order detail page like real ecommerce sites do.

    class Meta:
        ordering = ['created_at']
        # Always show log in chronological order — oldest first.
        # This gives a timeline view: Pending → Shipped → Out for Delivery → Delivered

    def __str__(self):
        return (
            f"{self.order.order_number}: "
            f"{self.old_status or 'created'} → {self.new_status}"
        )
    # e.g. "ORD-A3F2B1C4: pending → shipped"
    # Shows 'created' if old_status is empty (first log entry).