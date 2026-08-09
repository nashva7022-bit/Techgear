from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from users.views import landing

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing, name="landing"),
    path("admin-panel/", include("admin_panel.urls")),
    path("manage/", include("products.urls")),
    path("accounts/", include("allauth.urls")),
    path("store/", include("store.urls")),
    path("", include("users.urls")),
    path("orders/", include("orders.urls", namespace="orders")),
    path("manage/orders/", include("admin_orders.urls", namespace="admin_orders")),
    path("wallet/", include("wallet.urls", namespace="wallet")),
    path("manage/offers/", include("offers.urls", namespace="offers")),
    path("manage/coupons/", include("coupons.urls", namespace="coupons")),
    path("reports/", include("reports.urls")),
    path("referrals/", include("referrals.urls", namespace="referrals")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
