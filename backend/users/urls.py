from django.urls import path
from . import views

urlpatterns =[
    
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),

    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),

 
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-otp/', views.forgot_otp, name='forgot_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('password-reset-sent/', views.password_reset_sent, name='password_reset_sent'),


    path('dashboard/', views.dashboard, name='dashboard'),

    path('profile/edit/', views.edit_profile, name='edit_profile'),
   
    path('profile/change-password/', views.change_password, name='change_password'),

    path('profile/change-email/', views.change_email_request, name='change_email'),
    path('profile/verify-email/', views.verify_email, name='verify_email'),

    path('addresses/', views.manage_addresses, name='manage_addresses'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('addresses/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    path('addresses/set-default/<int:pk>/', views.set_default_address, name='set_default_address'),

]