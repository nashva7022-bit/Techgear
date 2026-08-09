from django.urls import path

from . import views

app_name = "referrals"

urlpatterns = [
    path("my-referrals/", views.referral_dashboard, name="referral_dashboard"),
]
