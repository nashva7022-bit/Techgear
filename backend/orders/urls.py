

from django.urls import path

from . import views

app_name = 'orders'


urlpatterns = [

    # ── CHECKOUT 
    path(
        'checkout/',
        views.checkout,
        name='checkout',
    ),
   
    # ── ORDER SUCCESS 
    path(
        'success/<str:order_number>/',
        views.order_success,
        name='order_success',
    ),


    # ── ORDER LIST 
    path(
        'my-orders/',
        views.order_list,
        name='order_list',
    ),
    
    # ── ORDER DETAIL 
    path(
        'my-orders/<str:order_number>/',
        views.order_detail,
        name='order_detail',
    ),
  

    # ── CANCEL ENTIRE ORDER 
    path(
        'my-orders/<str:order_number>/cancel/',
        views.cancel_order_view,
        name='cancel_order',
    ),
   

    # ── CANCEL SINGLE ITEM 
    path(
        'my-orders/<str:order_number>/cancel-item/<int:item_id>/',
        views.cancel_item_view,
        name='cancel_item',
    ),
    
    path(
        'my-orders/<str:order_number>/return-item/<int:item_id>/',
        views.return_item_view,
        name='return_item',
    ),
   

    # ── PDF INVOICE DOWNLOAD 
    path(
        'my-orders/<str:order_number>/invoice/',
        views.download_invoice,
        name='download_invoice',
    ),
   

]