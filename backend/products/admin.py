from django.contrib import admin
from .models import (
    Category, CategorySpecTemplate,
    DeviceModel,
    Product, ProductVariant, VariantImage, ProductSpecification,
)
 
 
# ── Category ──────────────────────────────────────────────────────────────
 
class SpecTemplateInline(admin.TabularInline):
    model   = CategorySpecTemplate
    extra   = 2
    ordering = ['order']
    fields  = ['name', 'placeholder', 'order', 'is_required']
 
 
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'has_case_type', 'is_customizable', 'is_active', 'product_count']
    list_filter   = ['is_active', 'has_case_type', 'is_customizable']
    search_fields = ['name']
    inlines       = [SpecTemplateInline]
    prepopulated_fields = {'slug': ('name',)}
 
 
# ── Device Model ──────────────────────────────────────────────────────────
# This is where admin adds new phone/laptop models.
# Populate this before adding products.
 
@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'is_active']
    list_filter   = ['brand', 'is_active']
    search_fields = ['name']
    ordering      = ['brand', 'name']
 
 
# ── Product ───────────────────────────────────────────────────────────────
 
class VariantImageInline(admin.TabularInline):
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


from store.models import Review  # add this import

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ['product', 'user', 'rating', 'created_at']
    list_filter   = ['rating']
    search_fields = ['product__name', 'user__email']
    readonly_fields = ['created_at']
