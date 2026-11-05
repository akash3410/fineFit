# Catalog admin registrations
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import Category, Event, Product, ProductVariant, ProductImage, Subcategory


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "is_deleted", "image_tag", "created_at")
    list_filter = ("is_active", "is_deleted", "parent")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at", "deleted_at", "image_tag")
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "slug", "description", "parent")
        }),
        ("Media", {
            "fields": ("image", "image_tag")
        }),
        ("Status", {
            "fields": ("is_active", "is_deleted", "deleted_at")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60" height="60" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return "-"
    image_tag.short_description = "Image"


@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "category", "is_active", "is_deleted", "created_at")
    list_filter = ("category", "is_active", "is_deleted")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category__name", "name")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("category", "name", "slug", "description")
        }),
        ("Status", {
            "fields": ("is_active", "is_deleted", "deleted_at")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ("title", "is_active", "start_at", "end_at", "created_at")
    list_filter = ("is_active", "start_at", "end_at")
    search_fields = ("title", "slug", "announcement")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "slug", "announcement")
        }),
        ("Date Range", {
            "fields": ("start_at", "end_at")
        }),
        ("Call to Action", {
            "fields": ("cta_label", "cta_link")
        }),
        ("Media", {
            "fields": ("image",)
        }),
        ("Status", {
            "fields": ("is_active", "is_deleted", "deleted_at")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("sku", "size", "color_name", "color_code", "price_override", "stock", "is_active")
    readonly_fields = ("id",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image_tag", "image", "alt_text", "display_order", "is_primary", "variant")
    readonly_fields = ("id", "image_tag")

    def image_tag(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return "-"
    image_tag.short_description = "Preview"


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("title", "sku", "category", "subcategory", "price", "discount_price", "stock", "status", "is_published", "is_deleted", "created_at")
    list_filter = ("status", "is_published", "is_deleted", "category", "subcategory", "is_featured")
    search_fields = ("title", "slug", "sku", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("status", "is_published")
    ordering = ("-created_at",)
    inlines = [ProductVariantInline, ProductImageInline]
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "slug", "sku", "description")
        }),
        ("Categorization", {
            "fields": ("category", "subcategory")
        }),
        ("Pricing & Inventory", {
            "fields": ("price", "discount_price", "stock")
        }),
        ("Status & Visibility", {
            "fields": ("status", "is_published", "is_featured")
        }),
        ("Soft Delete", {
            "fields": ("is_deleted", "deleted_at"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    class Media:
        js = ('js/dynamic_subcategory.js',)


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = ("sku", "product", "size", "color_name", "price_override", "stock", "is_active")
    list_filter = ("is_active", "size")
    search_fields = ("sku", "product__title")
    ordering = ("product__title", "size", "color_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    list_display = ("id", "product", "variant", "image_tag", "display_order", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("product__title",)
    ordering = ("product__title", "display_order")
    readonly_fields = ("created_at", "updated_at", "image_tag")

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="60" height="60" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return "-"
    image_tag.short_description = "Preview"
