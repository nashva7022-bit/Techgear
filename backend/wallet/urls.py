from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('', views.wallet_view, name='wallet'),
    path('topup/', views.wallet_topup_initiate, name='topup'),
    path('topup/callback/', views.wallet_topup_callback, name='topup_callback'),
    path('topup/failed/', views.wallet_topup_failed, name='topup_failed'),
]