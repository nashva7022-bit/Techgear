from django.urls import path
from . import views

app_name = 'admin_orders'

urlpatterns = [

    # Order list
    path('', views.order_list, name='order_list'),

    # Inventory
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/<int:variant_id>/update-stock/', views.update_stock, name='update_stock'),

    # Activity log
    path('activity/', views.activity_log, name='activity_log'),

    # RETURN REQUESTS
    path('returns/', views.return_requests, name='return_requests'),

    # ORDER DETAIL & STATUS 
   
    path('<str:order_number>/', views.order_detail, name='order_detail'),
    path('<str:order_number>/change-status/', views.change_status, name='change_status'),

    # APPROVE / REJECT RETURN
    path('<str:order_number>/items/<int:item_id>/approve-return/', views.approve_return_view, name='approve_return'),
    path('<str:order_number>/items/<int:item_id>/reject-return/',  views.reject_return_view,  name='reject_return'),

    path('<str:order_number>/items/<int:item_id>/cancel/', views.admin_cancel_item, name='admin_cancel_item'),

]