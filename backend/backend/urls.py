"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from users.views import landing  
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', landing, name='landing'),
    path('admin-panel/', include('admin_panel.urls')),
    path('manage/', include('products.urls')),   

    
    path('accounts/', include('allauth.urls')),
    path('store/', include('store.urls')),
    path('', include('users.urls')),

    path('orders/', include('orders.urls', namespace='orders')),
    path('manage/orders/', include('admin_orders.urls', namespace='admin_orders')),

    path('wallet/', include('wallet.urls', namespace='wallet')),

    path('manage/offers/', include('offers.urls', namespace='offers')),
    path('manage/coupons/', include('coupons.urls', namespace='coupons')),
   
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)