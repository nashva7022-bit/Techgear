# urls.py maps URLs to views.
# Think of it like a reception desk — someone comes in asking for a specific
# URL, this file looks it up and sends them to the right view function.
# Without this file, Django wouldn't know which view to call for which URL.

from django.urls import path
# path() is Django's function for defining a URL pattern.
# It takes: the URL pattern, the view function, and a name.
# Without path(), we can't define any URLs.

from . import views
# Imports all our view functions from views.py in this same folder.
# The dot (.) means "from the current app" — which is the orders app.
# Without this, we'd have to write the full path like 'orders.views'.

app_name = 'orders'
# This sets a namespace for all URLs in this file.
# It means we can refer to URLs as 'orders:checkout' instead of just 'checkout'.
# This prevents name conflicts — if another app also has a view called
# 'checkout', Django would get confused without namespaces.
# With app_name set, each app's URLs are clearly separated.

urlpatterns = [

    # ── CHECKOUT ──────────────────────────────────────────────────────────
    path(
        'checkout/',
        views.checkout,
        name='checkout',
    ),
    # URL: /orders/checkout/
    # Shows the checkout page (GET) and places the order (POST).
    # name='checkout' lets us write {% url 'orders:checkout' %} in templates
    # and redirect('orders:checkout') in views — no hardcoded URLs anywhere.
    # If we ever change the URL from 'checkout/' to 'buy/', we only change
    # it here — all templates and views update automatically.

    # ── ORDER SUCCESS ──────────────────────────────────────────────────────
    path(
        'success/<str:order_number>/',
        views.order_success,
        name='order_success',
    ),
    # URL: /orders/success/ORD-A3F2B1C4/
    # Shows the "Thank you for your order!" page after placing an order.
    # <str:order_number> is a URL parameter — Django captures whatever is
    # in that part of the URL and passes it to the view as order_number.
    # We use the order_number (like ORD-A3F2B1C4) instead of the database ID
    # because it's more readable and doesn't expose internal DB IDs.

    # ── ORDER LIST ─────────────────────────────────────────────────────────
    path(
        'my-orders/',
        views.order_list,
        name='order_list',
    ),
    # URL: /orders/my-orders/
    # Shows the user's full order history with search and pagination.
    # 'my-orders' is a clean, user-friendly URL — better than 'orders/list/'.

    # ── ORDER DETAIL ───────────────────────────────────────────────────────
    path(
        'my-orders/<str:order_number>/',
        views.order_detail,
        name='order_detail',
    ),
    # URL: /orders/my-orders/ORD-A3F2B1C4/
    # Shows the full detail page for one specific order.
    # <str:order_number> captures the order number from the URL.
    # Using order_number instead of pk (database ID) is more professional
    # and also a security measure — database IDs are predictable (1, 2, 3),
    # order numbers are random (ORD-A3F2B1C4) so harder to guess.

    # ── CANCEL ENTIRE ORDER ────────────────────────────────────────────────
    path(
        'my-orders/<str:order_number>/cancel/',
        views.cancel_order_view,
        name='cancel_order',
    ),
    # URL: /orders/my-orders/ORD-A3F2B1C4/cancel/
    # POST only (enforced by require_POST in the view).
    # Cancels the entire order and restores stock for all items.
    # The order number in the URL ties the cancel action to a specific order
    # so there's no ambiguity about which order is being cancelled.

    # ── CANCEL SINGLE ITEM ─────────────────────────────────────────────────
    path(
        'my-orders/<str:order_number>/cancel-item/<int:item_id>/',
        views.cancel_item_view,
        name='cancel_item',
    ),
    # URL: /orders/my-orders/ORD-A3F2B1C4/cancel-item/42/
    # POST only. Cancels just one item from the order.
    # <int:item_id> captures the OrderItem database ID.
    # We use int: here (not str:) because item IDs are always integers.
    # int: also automatically rejects non-numeric values — extra safety.
    # The order_number in the URL is an extra security layer — the view
    # checks that item 42 actually belongs to order ORD-A3F2B1C4.

    # ── RETURN SINGLE ITEM ─────────────────────────────────────────────────
    path(
        'my-orders/<str:order_number>/return-item/<int:item_id>/',
        views.return_item_view,
        name='return_item',
    ),
    # URL: /orders/my-orders/ORD-A3F2B1C4/return-item/42/
    # POST only. Returns one item from a delivered order.
    # Same structure as cancel-item but for returns.
    # Reason is mandatory — enforced in both view and service.

    # ── PDF INVOICE DOWNLOAD ───────────────────────────────────────────────
    path(
        'my-orders/<str:order_number>/invoice/',
        views.download_invoice,
        name='download_invoice',
    ),
    # URL: /orders/my-orders/ORD-A3F2B1C4/invoice/
    # GET request — user clicks a link, browser downloads the PDF.
    # No POST needed because we're not changing any data, just reading it.
    # Only available for delivered or cancelled orders (checked in view).

]