from django.urls import path
from . import views

urlpatterns = [
    # The login page
     path('login/', views.admin_login, name='admin_login'),
     path('logout/', views.admin_logout, name='admin_logout'),
    
    # User management
    path('users/', views.user_list, name='admin_user_management'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_block_user'),

   #dashboard
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
]