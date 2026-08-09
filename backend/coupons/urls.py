from django.urls import path

from . import views

app_name = "coupons"

urlpatterns = [
    path("", views.coupon_list, name="coupon_list"),
    path("create/", views.coupon_create, name="coupon_create"),
    path("edit/<int:pk>/", views.coupon_edit, name="coupon_edit"),
    path("<int:pk>/toggle/", views.toggle_coupon, name="toggle_coupon"),
    path("<int:pk>/delete/", views.delete_coupon, name="delete_coupon"),
]
