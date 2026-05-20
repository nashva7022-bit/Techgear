from django.urls import path
from . import views

urlpatterns = [
    # Product List — browse all products
    path('products/', views.product_list, name='product_list'),

    # Product Detail — single product page
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/customise/<int:item_id>/', views.update_cart_customisation, name='update_cart_customisation'),

    # Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/move/<int:item_id>/', views.move_to_cart, name='move_to_cart'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),

    path('products/<int:product_id>/review/', views.submit_review, name='submit_review'),
]
