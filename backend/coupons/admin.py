
from django.contrib import admin
from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display  = ['code', 'discount_type', 'discount_value', 'min_order_amount', 'is_active', 'start_date', 'end_date']
    list_filter   = ['discount_type', 'is_active']
    search_fields = ['code', 'description']
    readonly_fields = ['created_at']


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display  = ['coupon', 'user', 'used_at']
    list_filter   = ['coupon', 'used_at']
    search_fields = ['coupon__code', 'user__email']
    readonly_fields = ['used_at']