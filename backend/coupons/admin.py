from django.contrib import admin
from django import forms
from .models import Coupon, CouponUsage


class CouponAdminForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        min_order_amount = cleaned_data.get('min_order_amount')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Validate percentage discount (max 90%)
        if discount_type == 'percentage' and discount_value:
            if discount_value > 90:
                self.add_error('discount_value', 'Percentage discount cannot exceed 90%.')
            if discount_value <= 0:
                self.add_error('discount_value', 'Discount value must be greater than 0.')
        
        # Validate fixed discount minimum
        if discount_type == 'fixed' and discount_value and min_order_amount:
            if min_order_amount <= discount_value:
                self.add_error('min_order_amount', 
                    f'Minimum order amount must exceed the discount value (₹{discount_value}) for fixed discounts.')
        
        # Validate discount value for fixed
        if discount_type == 'fixed' and discount_value and discount_value <= 0:
            self.add_error('discount_value', 'Discount value must be greater than 0.')
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'End date must be after start date.')
        
        return cleaned_data


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    form = CouponAdminForm
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