from django.urls import path

from . import views

print("ADMIN PANEL URLS LOADED")

urlpatterns = [
    # Categories
    path("categories/", views.category_list, name="admin_category_list"),
    path("categories/add/", views.category_add, name="admin_category_add"),
    path("categories/edit/<int:pk>/", views.category_edit, name="admin_category_edit"),
    path(
        "categories/toggle/<int:pk>/",
        views.category_toggle_status,
        name="admin_category_toggle_status",
    ),
    path("categories/<int:pk>/", views.category_detail, name="admin_category_detail"),
    # AJAX — returns has_case_type flag + spec templates for a category
    path("categories/<int:pk>/meta/", views.category_meta, name="admin_category_meta"),
    # Products
    path("products/", views.product_list, name="admin_product_list"),
    path("products/add/", views.product_add, name="admin_product_add"),
    path("products/edit/<int:pk>/", views.product_edit, name="admin_product_edit"),
    path(
        "products/toggle/<int:pk>/",
        views.product_toggle_status,
        name="admin_product_toggle_status",
    ),
    path(
        "products/toggle-featured/<int:pk>/",
        views.product_toggle_featured,
        name="admin_product_toggle_featured",
    ),
    path(
        "products/toggle-trending/<int:pk>/",
        views.product_toggle_trending,
        name="admin_product_toggle_trending",
    ),
    # Variants
    path(
        "variants/toggle/<int:pk>/",
        views.variant_toggle_status,
        name="admin_variant_toggle_status",
    ),
    # API
    # Returns device models filtered by brand — used by product form JS dropdowns
    path(
        "api/device-models/",
        views.device_models_by_brand,
        name="admin_api_device_models",
    ),
]
