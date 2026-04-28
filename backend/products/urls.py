from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.category_list, name='admin_category_list'),
    path('categories/add/', views.category_add, name='admin_category_add'),
    path('categories/edit/<int:pk>/', views.category_edit, name='admin_category_edit'),
    path('categories/delete/<int:pk>/', views.category_delete, name='admin_category_delete'),
    path('categories/<int:pk>/', views.category_detail, name='admin_category_detail'),

    # Products
    path('products/', views.product_list, name='admin_product_list'),
    path('products/add/', views.product_add, name='admin_product_add'),
    path('products/edit/<int:pk>/', views.product_edit, name='admin_product_edit'),
    path('products/delete/<int:pk>/', views.product_delete, name='admin_product_delete'),

    # Variants
    path('variants/', views.variant_list, name='admin_variant_list'),
]