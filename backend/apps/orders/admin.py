"""Django admin for orders: staff review order contents and advance status."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Order, OrderItem, OrderStatusChange


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = (
        "product_title",
        "variant_sku",
        "size",
        "color_name",
        "unit_price",
        "quantity",
        "returned_quantity",
        "line_total",
    )
    readonly_fields = fields


class OrderStatusChangeInline(admin.TabularInline):
    model = OrderStatusChange
    extra = 0
    can_delete = False
    fields = ("previous_status", "new_status", "changed_by", "note", "created_at")
    readonly_fields = fields
    verbose_name_plural = "Status audit trail"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name",
        "customer_phone",
        "status",
        "payment_method",
        "total",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    list_select_related = ("user",)
    search_fields = ("order_number", "customer_name", "customer_phone", "customer_email")
    # Status is intentionally read-only here: it must only change through
    # OrderService.update_status(), which records the audit trail and restocks
    # cancelled/returned units. Editing it in Django admin would skip both.
    readonly_fields = (
        "dashboard_link",
        "status",
        "order_number",
        "user",
        "session_key",
        "customer_name",
        "customer_email",
        "customer_phone",
        "shipping_address",
        "notes",
        "payment_method",
        "subtotal",
        "shipping_fee",
        "total",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline, OrderStatusChangeInline]

    @admin.display(description="Fulfilment")
    def dashboard_link(self, obj):
        if not obj.pk:
            return "Save the order first."
        url = reverse(
            "admin_panel:order_view", kwargs={"order_number": obj.order_number}
        )
        return format_html(
            '<a href="{}">Confirm, ship, cancel or return this order in the '
            "staff dashboard</a>",
            url,
        )
