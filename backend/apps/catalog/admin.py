from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("sku", "size", "color_name", "color_code", "price_override", "is_active")
    readonly_fields = ("id",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "alt_text", "display_order", "is_primary", "variant")
    readonly_fields = ("id",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "category", "base_price", "is_published", "created_at")
    list_filter = ("is_published", "category")
    search_fields = ("title", "slug", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_published",)
    ordering = ("-created_at",)
    inlines = [ProductVariantInline, ProductImageInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "size", "color_name", "price_override", "is_active")
    list_filter = ("is_active", "size")
    search_fields = ("sku", "product__title")
    ordering = ("product__title", "size", "color_name")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "variant", "display_order", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("product__title",)
    ordering = ("product__title", "display_order")
