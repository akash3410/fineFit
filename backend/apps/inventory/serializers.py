"""
Serializers for the inventory domain.
"""

from rest_framework import serializers

from apps.catalog.models import ProductVariant
from .models import MovementReason, StockMovement, StockRecord


class StockRecordSerializer(serializers.ModelSerializer):
    """Staff serializer for StockRecord balances."""

    variant_id = serializers.UUIDField(source="variant.id", read_only=True)
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    variant_title = serializers.CharField(source="variant.product.title", read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockRecord
        fields = [
            "id",
            "variant_id",
            "variant_sku",
            "variant_title",
            "quantity_on_hand",
            "quantity_reserved",
            "available_quantity",
            "low_stock_threshold",
            "is_in_stock",
            "is_low_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StockRecordCreateSerializer(serializers.Serializer):
    """Payload for staff creating a new StockRecord for a variant."""

    variant_id = serializers.UUIDField(required=True)
    quantity_on_hand = serializers.IntegerField(default=0, min_value=0)
    quantity_reserved = serializers.IntegerField(default=0, min_value=0)
    low_stock_threshold = serializers.IntegerField(default=5, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference_id = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_variant_id(self, value):
        if not ProductVariant.objects.filter(id=value).exists():
            raise serializers.ValidationError("Variant with this ID does not exist.")
        if StockRecord.objects.filter(variant_id=value).exists():
            raise serializers.ValidationError("A StockRecord already exists for this variant.")
        return value

    def validate(self, attrs):
        if attrs.get("quantity_reserved", 0) > attrs.get("quantity_on_hand", 0):
            raise serializers.ValidationError(
                {"quantity_reserved": "Reserved quantity cannot exceed quantity on hand."}
            )
        return attrs


class StockAdjustmentSerializer(serializers.Serializer):
    """Payload for staff adjusting variant inventory."""

    ACTION_CHOICES = (
        ("INCREASE", "Increase On-Hand Stock"),
        ("DECREASE", "Decrease On-Hand Stock"),
        ("SET", "Set Absolute On-Hand Count"),
        ("RESERVE", "Reserve Available Stock"),
        ("RELEASE", "Release Reserved Stock"),
    )

    action = serializers.ChoiceField(choices=ACTION_CHOICES, required=True)
    quantity = serializers.IntegerField(required=True, min_value=0)
    reason = serializers.ChoiceField(
        choices=MovementReason.choices,
        required=False,
        default=MovementReason.CORRECTION,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference_id = serializers.CharField(required=False, allow_blank=True, default="")
    from_reserved = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        action = attrs.get("action")
        quantity = attrs.get("quantity")

        if action in ("INCREASE", "DECREASE", "RESERVE", "RELEASE") and quantity <= 0:
            raise serializers.ValidationError(
                {"quantity": f"Quantity must be strictly greater than 0 for {action} action."}
            )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    """Staff read-only serializer for immutable movement audit logs."""

    variant_id = serializers.UUIDField(source="variant.id", read_only=True)
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "stock_record_id",
            "variant_id",
            "variant_sku",
            "quantity_delta",
            "reserved_delta",
            "reason",
            "reason_display",
            "notes",
            "reference_id",
            "actor_email",
            "created_at",
        ]
        read_only_fields = fields


class PublicVariantAvailabilitySerializer(serializers.Serializer):
    """
    Carefully defined derived availability representation for public storefronts.

    Never exposes exact on-hand balances to prevent competitor scraping.
    """

    variant_id = serializers.UUIDField()
    sku = serializers.CharField()
    is_in_stock = serializers.BooleanField()
    is_low_stock = serializers.BooleanField()
    status = serializers.ChoiceField(
        choices=["IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK"],
    )

