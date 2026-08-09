from django import forms
from django.utils import timezone

from .models import CategoryOffer, ProductOffer


class BaseOfferForm(forms.ModelForm):
    identity_field = None

    def __init__(self, *args, is_edit=False, **kwargs):
        self.is_edit = is_edit
        super().__init__(*args, **kwargs)
        if is_edit and self.identity_field:
            self.fields.pop(self.identity_field, None)

    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        if not self.is_edit and start_date and start_date < timezone.now().date():
            raise forms.ValidationError("Start date cannot be in the past.")
        return start_date


class ProductOfferForm(BaseOfferForm):
    identity_field = "product"

    class Meta:
        model = ProductOffer
        fields = ["product", "discount_percent", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class CategoryOfferForm(BaseOfferForm):
    identity_field = "category"

    class Meta:
        model = CategoryOffer
        fields = ["category", "discount_percent", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
