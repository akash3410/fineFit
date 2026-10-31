"""
Django admin configuration for inventory models.

StockMovement is strictly read-only within the admin interface to preserve audit integrity.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import StockMovement, StockRecord


@admin.register(StockRecord)
class StockRecordAdmin(admin.ModelAdmin):
    list_display = [
        "get_sku",
        "get_product_title",
        "quantity_on_hand",
        "quantity_reserved",
        "get_available_quantity",
        "low_stock_threshold",
        "get_in_stock",
        "get_low_stock",
        "updated_at",
    ]
    list_filter = ["low_stock_threshold"]
    search_fields = ["variant__sku", "variant__product__title"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "get_available_quantity",
        "get_in_stock",
        "get_low_stock",
    ]

    @admin.display(description=_("SKU"), ordering="variant__sku")
    def get_sku(self, obj):
        return obj.variant.sku if obj.variant else "-"

    @admin.display(description=_("Product"), ordering="variant__product__title")
    def get_product_title(self, obj):
        return obj.variant.product.title if obj.variant and obj.variant.product else "-"

    @admin.display(description=_("Available"))
    def get_available_quantity(self, obj):
        return obj.available_quantity

    @admin.display(description=_("In Stock"), boolean=True)
    def get_in_stock(self, obj):
        return obj.is_in_stock

    @admin.display(description=_("Low Stock"), boolean=True)
    def get_low_stock(self, obj):
        return obj.is_low_stock


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """
    Immutable audit trail viewer in Django admin.
    No addition, modification, or deletion permitted via the admin console.
    """

    list_display = [
        "created_at",
        "get_sku",
        "quantity_delta",
        "reserved_delta",
        "reason",
        "actor",
        "reference_id",
    ]
    list_filter = ["reason", "created_at"]
    search_fields = ["variant__sku", "reference_id", "actor__email", "notes"]
    readonly_fields = [
        "id",
        "stock_record",
        "variant",
        "quantity_delta",
        "reserved_delta",
        "reason",
        "notes",
        "reference_id",
        "actor",
        "created_at",
    ]

    @admin.display(description=_("SKU"), ordering="variant__sku")
    def get_sku(self, obj):
        return obj.variant.sku if obj.variant else "-"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

