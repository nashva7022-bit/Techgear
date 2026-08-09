from django import forms
from django.core.exceptions import ValidationError

from .models import (Category, Product, ProductSpecification, ProductVariant,
                     VariantImage)

# CATEGORY FORM


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "image", "is_customizable", "is_active"]

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Category name is required.")
        qs = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A category with this name already exists.")
        return name


# PRODUCT FORM


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "brand", "category", "is_active", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True
        ).order_by("name")
        self.fields["category"].empty_label = "Select a category"

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Product name is required.")
        qs = Product.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A product with this name already exists.")
        return name


# PRODUCT SPECIFICATION FORM


class ProductSpecificationForm(forms.ModelForm):
    class Meta:
        model = ProductSpecification
        fields = ["name", "value", "order"]

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Specification name is required.")
        return name

    def clean_value(self):
        value = self.cleaned_data.get("value", "").strip()
        if not value:
            raise ValidationError("Specification value is required.")
        return value


# PRODUCT VARIANT FORM


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            "device_model",
            "case_type",
            "color",
            "color_code",
            "sku",
            "price",
            "stock",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].required = False
        self.fields["case_type"].required = False

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None:
            raise ValidationError("Price is required.")
        if price <= 0:
            raise ValidationError("Price must be greater than 0.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is None:
            raise ValidationError("Stock quantity is required.")
        if stock < 0:
            raise ValidationError("Stock cannot be negative.")
        return stock

    def clean_color_code(self):
        code = self.cleaned_data.get("color_code", "").strip()
        if not code.startswith("#") or len(code) != 7:
            raise ValidationError("Enter a valid hex color code (e.g. #FF0000).")
        return code

    def clean_sku(self):
        sku = self.cleaned_data.get("sku", "").strip()
        if sku:
            qs = ProductVariant.objects.filter(sku__iexact=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("This SKU is already in use.")
        return sku
