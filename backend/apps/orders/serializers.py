"""Order serializers.

The write serializer accepts only customer/delivery data plus the payment
method — never prices, totals, status or ownership identifiers. Every monetary
value in the read serializers comes from the stored order snapshot.
"""

import re

from rest_framework import serializers

from .models import (
    Order,
    OrderItem,
    OrderStatusChange,
    PaymentMethod,
    ReturnRequest,
    ReturnRequestItem,
    ReturnRequestStatus,
)
from .services import CUSTOMER_RETURNABLE_STATUSES

#: Digits, spaces, dashes and an optional leading ``+`` (BD local/international).
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s-]{6,19}$")


class ShippingAddressSerializer(serializers.Serializer):
    """Structured delivery address stored as a JSON snapshot on the order."""

    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    city = serializers.CharField(max_length=120)
    area = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    country = serializers.CharField(
        max_length=80, required=False, allow_blank=True, default="Bangladesh"
    )


class OrderCreateSerializer(serializers.Serializer):
    """Validated checkout payload for a cash-on-delivery order."""

    customer_name = serializers.CharField(max_length=255)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True, default="")
    shipping_address = ShippingAddressSerializer()
    notes = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )
    payment_method = serializers.ChoiceField(
        choices=[PaymentMethod.COD], default=PaymentMethod.COD
    )

    def validate_customer_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate_customer_phone(self, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.match(value):
            raise serializers.ValidationError(
                "Enter a valid phone number (digits, spaces, dashes or a leading +)."
            )
        return value


class OrderItemReadSerializer(serializers.ModelSerializer):
    """Purchased line snapshot with its return progress."""

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_title",
            "variant_sku",
            "size",
            "color_name",
            "unit_price",
            "quantity",
            "returned_quantity",
            "remaining_quantity",
            "line_total",
        ]
        read_only_fields = fields


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """Customer-safe view of the audit trail (no staff identities)."""

    class Meta:
        model = OrderStatusChange
        fields = ["previous_status", "new_status", "note", "created_at"]
        read_only_fields = fields


class ReturnRequestItemReadSerializer(serializers.ModelSerializer):
    """Requested units of one order line."""

    item_id = serializers.IntegerField(source="order_item_id", read_only=True)
    product_title = serializers.CharField(
        source="order_item.product_title", read_only=True
    )
    variant_sku = serializers.CharField(
        source="order_item.variant_sku", read_only=True
    )

    class Meta:
        model = ReturnRequestItem
        fields = ["item_id", "product_title", "variant_sku", "quantity"]
        read_only_fields = fields


class ReturnRequestReadSerializer(serializers.ModelSerializer):
    """A customer's return request and how staff resolved it."""

    items = ReturnRequestItemReadSerializer(many=True, read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReturnRequest
        fields = [
            "id",
            "status",
            "reason",
            "staff_note",
            "items",
            "total_quantity",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields


class ReturnRequestItemWriteSerializer(serializers.Serializer):
    """One line of a return request: which order item, how many units."""

    item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class ReturnRequestCreateSerializer(serializers.Serializer):
    """Validated payload for a customer return request."""

    reason = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )
    items = ReturnRequestItemWriteSerializer(many=True, allow_empty=False)

    def validate_items(self, value):
        seen: set[int] = set()
        for item in value:
            if item["item_id"] in seen:
                raise serializers.ValidationError(
                    "Each order item can only appear once."
                )
            seen.add(item["item_id"])
        return value


class OrderReadSerializer(serializers.ModelSerializer):
    """Order detail for the customer who owns it (and staff in the admin)."""

    items = OrderItemReadSerializer(many=True, read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    status_history = OrderStatusHistorySerializer(
        source="status_changes", many=True, read_only=True
    )
    return_requests = ReturnRequestReadSerializer(many=True, read_only=True)
    can_request_return = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "payment_method",
            "customer_name",
            "customer_email",
            "customer_phone",
            "shipping_address",
            "notes",
            "subtotal",
            "shipping_fee",
            "total",
            "total_quantity",
            "items",
            "status_history",
            "return_requests",
            "can_request_return",
            "created_at",
        ]
        read_only_fields = fields

    def get_can_request_return(self, obj) -> bool:
        """Whether the customer may open a new return request right now."""
        if obj.status not in CUSTOMER_RETURNABLE_STATUSES:
            return False
        if any(
            request.status == ReturnRequestStatus.REQUESTED
            for request in obj.return_requests.all()
        ):
            return False
        return any(item.remaining_quantity for item in obj.items.all())
