
from django.urls import path
from . import views
from products.views import device_models_by_brand

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),

    path('users/', views.user_list, name='admin_user_management'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_block_user'),

    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    
    path('api/device-models/', device_models_by_brand, name='admin_api_device_models'),

    path('settings/', views.site_settings, name='admin_site_settings'),

    path('wallets/', views.admin_wallet_list, name='admin_wallet_list'),
    path('wallets/<int:user_id>/', views.admin_wallet_detail, name='admin_wallet_detail'),

    path('wallets/<int:user_id>/credit/', views.admin_wallet_credit, name='admin_wallet_credit'),

    
]