"""
Cart serializers.

Read serializers compute every monetary value and stock figure from trusted
server-side data (``variant.effective_price``, ``StockRecord``); no
client-supplied prices, totals, availability or owner identifiers are ever
serialized or accepted. Write serializers accept only ``variant_id`` and
``quantity`` — nothing else — enforcing the platform's trust boundary.
"""

from rest_framework import serializers

from apps.catalog.models import ProductVariant

from .models import Cart, CartItem


class CartVariantMiniSerializer(serializers.ModelSerializer):
    """Compact trusted variant info shown on cart lines."""

    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "size",
            "color_name",
            "color_code",
            "is_active",
            "product_title",
            "product_slug",
        ]
        read_only_fields = fields


class CartItemSerializer(serializers.ModelSerializer):
    """Public representation of a cart line with trusted pricing/stock."""

    variant = CartVariantMiniSerializer(read_only=True)
    image = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    has_sufficient_stock = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "image",
            "unit_price",
            "quantity",
            "line_total",
            "available_quantity",
            "is_available",
            "has_sufficient_stock",
            "created_at",
        ]
        read_only_fields = fields

    def get_image(self, obj) -> str | None:
        """Product image where available: variant-specific primary, else product primary."""
        product = obj.variant.product
        images = list(product.images.all())  # expects prefetched images relation
        chosen = None
        for img in images:
            if img.variant_id == obj.variant.id:
                chosen = img
                break
        if chosen is None:
            chosen = next((img for img in images if img.is_primary), images[0] if images else None)
        if chosen is None:
            return None
        image_field = chosen.image
        if not image_field:
            return None
        request = self.context.get("request")
        url = image_field.url
        return request.build_absolute_uri(url) if request else url

    def get_unit_price(self, obj) -> str | None:
        return str(obj.unit_price) if obj.unit_price is not None else None

    def get_line_total(self, obj) -> str | None:
        return str(obj.line_total) if obj.line_total is not None else None

    def get_available_quantity(self, obj) -> int:
        """Current sellable units (advisory; derived from inventory source of truth)."""
        return obj.available_quantity

    def get_is_available(self, obj) -> bool:
        return obj.is_available

    def get_has_sufficient_stock(self, obj) -> bool:
        return obj.has_sufficient_stock


class CartSerializer(serializers.ModelSerializer):
    """Current cart representation: items, totals and conflict indicators."""

    items = CartItemSerializer(many=True, read_only=True)
    total_quantity = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    has_stock_conflicts = serializers.SerializerMethodField()
    conflicts = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_quantity",
            "subtotal",
            "has_stock_conflicts",
            "conflicts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_total_quantity(self, obj) -> int:
        return obj.total_quantity

    def get_subtotal(self, obj) -> str:
        return str(obj.subtotal) if obj.subtotal is not None else "0.00"

    def get_has_stock_conflicts(self, obj) -> bool:
        return self.get_conflicts(obj) != []

    def get_conflicts(self, obj) -> list[dict]:
        """Current stock conflicts the customer should review before checkout."""
        conflicts = []
        for item in obj.items.all():
            if item.has_sufficient_stock:
                continue
            stock_record = getattr(item.variant, "stock_record", None)
            conflicts.append(
                {
                    "cart_item_id": item.pk,
                    "variant_id": str(item.variant_id),
                    "sku": item.variant.sku,
                    "quantity": item.quantity,
                    "available_quantity": item.available_quantity,
                    "reason": (
                        "OUT_OF_STOCK"
                        if stock_record is None or item.available_quantity == 0
                        else "INSUFFICIENT_STOCK"
                    ),
                }
            )
        return conflicts


class AddCartItemSerializer(serializers.Serializer):
    """Accepts ONLY a variant reference and quantity; nothing else."""

    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    """Accepts ONLY a quantity; item identity comes from the URL path."""

    quantity = serializers.IntegerField(min_value=1)
