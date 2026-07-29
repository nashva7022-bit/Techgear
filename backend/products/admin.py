from django.contrib import admin
from django import forms
from .models import (
    Category, CategorySpecTemplate,
    DeviceModel,
    Product, ProductVariant, VariantImage, ProductSpecification,
)



class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if image.content_type not in allowed_types:
                raise forms.ValidationError('Only JPG, PNG, and WebP images are allowed.')
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image size must not exceed 5MB.')
        return image


class VariantImageAdminForm(forms.ModelForm):
    class Meta:
        model = VariantImage
        fields = '__all__'
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if image.content_type not in allowed_types:
                raise forms.ValidationError('Only JPG, PNG, and WebP images are allowed.')
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image size must not exceed 5MB.')
        return image


# ADMIN CLASSES

class SpecTemplateInline(admin.TabularInline):
    model   = CategorySpecTemplate
    extra   = 2
    ordering = ['order']
    fields  = ['name', 'placeholder', 'order', 'is_required']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display  = ['name', 'has_case_type', 'is_customizable', 'is_active', 'product_count']
    list_filter   = ['is_active', 'has_case_type', 'is_customizable']
    search_fields = ['name']
    inlines       = [SpecTemplateInline]
    prepopulated_fields = {'slug': ('name',)}
    
    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'is_active']
    list_filter   = ['brand', 'is_active']
    search_fields = ['name']
    ordering      = ['brand', 'name']


class VariantImageInline(admin.TabularInline):
    form = VariantImageAdminForm
    model  = VariantImage
    extra  = 0
    fields = ['image', 'is_primary', 'order']


class ProductVariantInline(admin.TabularInline):
    model  = ProductVariant
    extra  = 0
    fields = ['device_model', 'case_type', 'color', 'sku', 'price', 'stock', 'is_active']
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'category', 'is_active','is_featured', 'is_trending', 'min_price', 'total_stock']
    list_filter   = ['brand', 'category', 'is_active']
    list_editable = ['is_featured', 'is_trending']
    search_fields = ['name', 'brand']
    inlines       = [ProductVariantInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display  = ['product', 'device_model', 'case_type', 'color', 'price', 'stock', 'is_active']
    list_filter   = ['color', 'case_type', 'is_active']
    search_fields = ['product__name', 'sku']
    inlines       = [VariantImageInline]


from store.models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ['product', 'user', 'rating', 'created_at']
    list_filter   = ['rating']
    search_fields = ['product__name', 'user__email']
    readonly_fields = ['created_at']