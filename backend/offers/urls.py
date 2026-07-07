from django.urls import path
from . import views

app_name = 'offers'

urlpatterns = [
    path('',                                    views.offer_list,             name='offer_list'),
    path('product/create/',                     views.product_offer_create,   name='product_offer_create'),
    path('category/create/',                    views.category_offer_create,  name='category_offer_create'),
    path('product/<int:pk>/toggle/',            views.toggle_product_offer,   name='toggle_product_offer'),
    path('category/<int:pk>/toggle/',           views.toggle_category_offer,  name='toggle_category_offer'),
    path('product/<int:pk>/delete/',            views.delete_product_offer,   name='delete_product_offer'),
    path('category/<int:pk>/delete/',           views.delete_category_offer,  name='delete_category_offer'),

    path('product/<int:pk>/edit/', views.product_offer_edit, name='product_offer_edit'),
    path('category/<int:pk>/edit/', views.category_offer_edit, name='category_offer_edit'),
]