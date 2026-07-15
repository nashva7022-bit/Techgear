from django import forms
from django.utils import timezone
from .models import Coupon


class CouponForm(forms.ModelForm):

    class Meta:
        model = Coupon
        fields = [
            'code', 'description', 'discount_type', 'discount_value',
            'max_discount_cap', 'min_order_amount', 'usage_limit',
            'start_date', 'end_date',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, is_edit=False, **kwargs):
        self.is_edit = is_edit
        super().__init__(*args, **kwargs)
        # blank min-order means "no minimum" → treat as 0, so don't force it
        self.fields['min_order_amount'].required = False

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        qs = Coupon.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A coupon with this code already exists.')
        return code

    def clean_min_order_amount(self):
        moa = self.cleaned_data.get('min_order_amount')
        if moa is None:
            return 0
        if moa < 0:
            raise forms.ValidationError('Minimum order amount cannot be negative.')
        if moa > 100000:
            raise forms.ValidationError('Minimum order amount seems too high.')
        return moa

    def clean_usage_limit(self):
        ul = self.cleaned_data.get('usage_limit')
        if ul is None:
            return None
        if ul <= 0:
            raise forms.ValidationError('Usage limit must be at least 1.')
        if self.is_edit and ul < self.instance.times_used:
            raise forms.ValidationError(
                f'Cannot set limit below current usage count ({self.instance.times_used}).'
            )
        return ul

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        # only block past start dates when creating — an existing coupon may
        # already have started in the past
        if not self.is_edit and start_date and start_date < timezone.now().date():
            raise forms.ValidationError('Start date cannot be in the past.')
        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        # only block past end dates when editing (create is already covered by
        # the future-start rule)
        if self.is_edit and end_date and end_date < timezone.now().date():
            raise forms.ValidationError('End date cannot be in the past.')
        return end_date

    def clean(self):
        cleaned = super().clean()
        dtype = cleaned.get('discount_type')
        dvalue = cleaned.get('discount_value')
        cap = cleaned.get('max_discount_cap')
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')

        # discount value depends on the type, so it's validated here
        if dvalue is not None:
            if dvalue <= 0:
                self.add_error('discount_value', 'Discount value must be greater than 0.')
            elif dtype == 'percentage' and dvalue > 90:
                self.add_error('discount_value', 'Percentage discount cannot exceed 90%.')
            elif dtype == 'fixed' and dvalue > 10000:
                self.add_error('discount_value', 'Fixed discount cannot exceed ₹10,000.')

        # cap only makes sense for percentage discounts
        if cap is not None:
            if dtype == 'fixed':
                self.add_error('max_discount_cap', 'Max cap only applies to percentage discounts.')
            elif cap <= 0:
                self.add_error('max_discount_cap', 'Enter a valid amount greater than 0.')
            elif cap > 10000:
                self.add_error('max_discount_cap', 'Cap cannot exceed ₹10,000.')

        # end must be strictly after start
        if start and end:
            if end < start:
                self.add_error('end_date', 'End date must be after start date.')
            elif end == start:
                self.add_error('end_date', 'End date must be after start date, not the same day.')

        return cleaned