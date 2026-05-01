from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/',                          views.category_list,          name='admin_category_list'),
    path('categories/add/',                      views.category_add,           name='admin_category_add'),
    path('categories/edit/<int:pk>/',            views.category_edit,          name='admin_category_edit'),
    path('categories/toggle/<int:pk>/',          views.category_toggle_status, name='admin_category_toggle_status'),
    path('categories/<int:pk>/',                 views.category_detail,        name='admin_category_detail'),

    # Products
    path('products/',                            views.product_list,           name='admin_product_list'),
    path('products/add/',                        views.product_add,            name='admin_product_add'),
    path('products/edit/<int:pk>/',              views.product_edit,           name='admin_product_edit'),
    path('products/toggle/<int:pk>/',            views.product_toggle_status,  name='admin_product_toggle_status'),

    # Variants
    path('variants/toggle/<int:pk>/',            views.variant_toggle_status,  name='admin_variant_toggle_status'),
]