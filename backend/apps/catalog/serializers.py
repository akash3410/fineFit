"""
Catalog serializers.

Read and write representations are deliberately separated:
  - Read serializers shape the public/storefront JSON (nested trees, primary
    image, effective variant price) and never expose internal bookkeeping.
  - Write serializers perform server-side validation (prices, colour codes,
    slug uniqueness, image file constraints) before persisting.

Multi-record writes (e.g. a product with nested variants) are wrapped in a
transaction at the view/serializer layer so a partial failure never leaves the
database inconsistent.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from PIL import Image
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    validate_color_code,
)

# ---------------------------------------------------------------------------
# Image file validation policy (single source of truth)
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_DIMENSION = 8000  # pixels (guards against decompression bombs)


def validate_image_file(file) -> None:
    """
    Validate an uploaded product image: size, decodability, format, dimensions.

    Raises ``ValidationError`` with an actionable message on any violation.
    Always resets the file pointer so downstream storage sees the full stream.
    """
    if file is None:
        raise ValidationError(_("An image file is required."))

    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError(
            _("Image file is too large. Maximum size is %(mb)s MB.")
            % {"mb": MAX_IMAGE_BYTES // (1024 * 1024)}
        )

    content_type = getattr(file, "content_type", None)
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(
            _("Unsupported image type. Allowed formats: JPEG, PNG, WebP.")
        )

    try:
        with Image.open(file) as img:
            img_format = (img.format or "").upper()
            width, height = img.size
    except Exception as exc:  # noqa: BLE001 - surface any decode failure as validation error
        raise ValidationError(_("The uploaded file is not a valid image.")) from exc
    finally:
        file.seek(0)

    if img_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(_("Unsupported image type. Allowed formats: JPEG, PNG, WebP."))

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValidationError(
            _("Image dimensions are too large. Maximum is %(max)s px per side.")
            % {"max": MAX_IMAGE_DIMENSION}
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _unique_slug_for(model_class, base: str, instance_pk=None) -> str:
    """
    Generate a slug unique for ``model_class``, appending ``-2``, ``-3``... on
    collision. ``instance_pk`` excludes the current object during updates.
    """
    slug = slugify(base)[:255] or "item"
    candidate = slug
    counter = 2
    while True:
        qs = model_class.objects.filter(slug=candidate)
        if instance_pk is not None:
            qs = qs.exclude(pk=instance_pk)
        if not qs.exists():
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1


# ---------------------------------------------------------------------------
# Read serializers (public / storefront)
# ---------------------------------------------------------------------------


class CategorySerializer(serializers.ModelSerializer):
    """Recursive category tree node (active categories only at the root)."""

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "is_active", "children"]

    def get_children(self, obj) -> list[dict]:
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True, context=self.context).data


class ProductImageReadSerializer(serializers.ModelSerializer):
    """Public representation of a product image (URL + metadata)."""

    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "display_order", "is_primary", "variant"]
        read_only_fields = fields


class ProductVariantReadSerializer(serializers.ModelSerializer):
    """Public representation of a variant, including the effective price and derived stock status."""

    effective_price = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "size",
            "color_name",
            "color_code",
            "is_active",
            "effective_price",
            "is_in_stock",
            "is_low_stock",
            "stock_status",
        ]
        read_only_fields = fields

    def get_effective_price(self, obj) -> str | None:
        base_price = self.context.get("base_price")
        price = obj.price_override if obj.price_override is not None else base_price
        return str(price) if price is not None else None

    def get_is_in_stock(self, obj) -> bool:
        stock_record = getattr(obj, "stock_record", None)
        return stock_record.is_in_stock if stock_record else False

    def get_is_low_stock(self, obj) -> bool:
        stock_record = getattr(obj, "stock_record", None)
        return stock_record.is_low_stock if stock_record else False

    def get_stock_status(self, obj) -> str:
        stock_record = getattr(obj, "stock_record", None)
        if not stock_record:
            return "OUT_OF_STOCK"
        if stock_record.is_in_stock:
            return "LOW_STOCK" if stock_record.is_low_stock else "IN_STOCK"
        return "OUT_OF_STOCK"


class ProductListSerializer(serializers.ModelSerializer):
    """Compact product card for list views (includes the primary image)."""

    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "title",
            "base_price",
            "category",
            "primary_image",
            "created_at",
        ]
        read_only_fields = fields

    def get_primary_image(self, obj) -> dict | None:
        images = list(obj.images.all())  # prefetched; ordered by display_order, then id
        if not images:
            return None
        primary = next((img for img in images if img.is_primary), images[0])
        return ProductImageReadSerializer(primary, context=self.context).data


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full product detail: description, all images, and active variants."""

    category = CategorySerializer(read_only=True)
    images = ProductImageReadSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "base_price",
            "category",
            "images",
            "variants",
            "created_at",
        ]
        read_only_fields = fields

    def get_variants(self, obj) -> list[dict]:
        variants = obj.variants.all()
        if not self.context.get("include_all_variants"):
            variants = variants.filter(is_active=True)
        return ProductVariantReadSerializer(
            variants,
            many=True,
            context={**self.context, "base_price": obj.base_price},
        ).data


# ---------------------------------------------------------------------------
# Write serializers (staff management)
# ---------------------------------------------------------------------------


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Create/update a category with slug uniqueness and parent integrity."""

    slug = serializers.SlugField(max_length=255, required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "is_active"]

    def validate(self, attrs):
        instance = Category(
            pk=self.instance.pk if self.instance else None,
            name=attrs.get("name", self.instance.name if self.instance else ""),
            slug=attrs.get("slug") or (self.instance.slug if self.instance else ""),
            parent=attrs.get("parent", self.instance.parent if self.instance else None),
            is_active=attrs.get("is_active", self.instance.is_active if self.instance else True),
        )
        instance.clean()
        return attrs

    def _ensure_slug(self, attrs):
        base = attrs.get("slug") or attrs.get("name") or "category"
        attrs["slug"] = _unique_slug_for(Category, base, self.instance.pk if self.instance else None)
        return attrs

    def create(self, validated_data):
        validated_data = self._ensure_slug(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get("slug"):
            validated_data.pop("slug", None)
        else:
            validated_data = self._ensure_slug(validated_data)
        return super().update(instance, validated_data)


class ProductVariantWriteSerializer(serializers.ModelSerializer):
    """Create/update a variant with SKU, colour, and price validation."""

    color_code = serializers.CharField(max_length=7, required=False, allow_blank=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "sku",
            "size",
            "color_name",
            "color_code",
            "price_override",
            "is_active",
        ]

    def validate_color_code(self, value: str) -> str:
        if value:
            try:
                validate_color_code(value)
            except DjangoValidationError as exc:
                raise ValidationError(exc.messages) from exc
        return value

    def validate_price_override(self, value):
        if value is not None and value < Decimal("0"):
            raise ValidationError(_("Price override cannot be negative."))
        return value

    def validate_sku(self, value: str) -> str:
        qs = ProductVariant.objects.filter(sku=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(_("A variant with this SKU already exists."))
        return value

    def validate(self, attrs):
        # Reuse the model's cross-field rules (duplicate size/colour, etc.).
        instance = ProductVariant(
            pk=self.instance.pk if self.instance else None,
            product=attrs.get("product", self.instance.product if self.instance else None),
            sku=attrs.get("sku", self.instance.sku if self.instance else ""),
            size=attrs.get("size", self.instance.size if self.instance else ""),
            color_name=attrs.get("color_name", self.instance.color_name if self.instance else ""),
            color_code=attrs.get("color_code", self.instance.color_code if self.instance else ""),
            price_override=attrs.get(
                "price_override", self.instance.price_override if self.instance else None
            ),
            is_active=attrs.get("is_active", self.instance.is_active if self.instance else True),
        )
        instance.clean()
        return attrs


class ProductImageWriteSerializer(serializers.ModelSerializer):
    """Create/update a product image with file and relationship validation."""

    image = serializers.ImageField(required=True)

    class Meta:
        model = ProductImage
        fields = ["id", "product", "variant", "image", "alt_text", "display_order", "is_primary"]
        # The model's partial unique constraint (one primary per product) is
        # enforced manually in ``validate`` below. DRF's auto-generated
        # UniqueTogetherValidator mis-handles partial constraints (it would also
        # reject additional non-primary images), so we suppress it here.
        validators = []

    def validate_image(self, file):
        validate_image_file(file)
        return file

    def validate(self, attrs):
        instance = ProductImage(
            pk=self.instance.pk if self.instance else None,
            product=attrs.get("product", self.instance.product if self.instance else None),
            variant=attrs.get("variant", self.instance.variant if self.instance else None),
            alt_text=attrs.get("alt_text", self.instance.alt_text if self.instance else ""),
            display_order=attrs.get(
                "display_order", self.instance.display_order if self.instance else 0
            ),
            is_primary=attrs.get(
                "is_primary", self.instance.is_primary if self.instance else False
            ),
        )
        # Cross-object rule: variant must belong to the same product.
        if instance.variant_id and instance.product_id:
            if instance.variant.product_id != instance.product_id:
                raise ValidationError({"variant": _("The selected variant does not belong to this product.")})
        # Enforce single-primary at the application layer (DB constraint is the backstop).
        if instance.is_primary and instance.product_id:
            conflicting = ProductImage.objects.filter(
                product_id=instance.product_id, is_primary=True
            ).exclude(pk=instance.pk).exists()
            if conflicting:
                raise ValidationError(
                    {"is_primary": _("This product already has a primary image.")}
                )
        return attrs


class ProductVariantNestedWriteSerializer(serializers.ModelSerializer):
    """Nested variant writes inside product creation (product assigned server-side)."""

    color_code = serializers.CharField(max_length=7, required=False, allow_blank=True)

    class Meta:
        model = ProductVariant
        fields = [
            "sku",
            "size",
            "color_name",
            "color_code",
            "price_override",
            "is_active",
        ]

    def validate_color_code(self, value: str) -> str:
        if value:
            try:
                validate_color_code(value)
            except DjangoValidationError as exc:
                raise ValidationError(exc.messages) from exc
        return value

    def validate_price_override(self, value):
        if value is not None and value < Decimal("0"):
            raise ValidationError(_("Price override cannot be negative."))
        return value

    def validate_sku(self, value: str) -> str:
        qs = ProductVariant.objects.filter(sku=value)
        if qs.exists():
            raise ValidationError(_("A variant with this SKU already exists."))
        return value

    def validate(self, attrs):
        instance = ProductVariant(
            sku=attrs.get("sku", ""),
            size=attrs.get("size", ""),
            color_name=attrs.get("color_name", ""),
            color_code=attrs.get("color_code", ""),
            price_override=attrs.get("price_override", None),
            is_active=attrs.get("is_active", True),
        )
        instance.clean()
        return attrs


class ProductWriteSerializer(serializers.ModelSerializer):
    """
    Create/update a product. Creation may include nested variants within a
    single transaction so a failure rolls back both product and variants.
    """

    slug = serializers.SlugField(max_length=255, required=False, allow_blank=True)
    base_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    variants = ProductVariantNestedWriteSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "title",
            "slug",
            "description",
            "base_price",
            "is_published",
            "variants",
        ]

    def validate_base_price(self, value):
        if value < Decimal("0"):
            raise ValidationError(_("Base price cannot be negative."))
        return value

    def _ensure_slug(self, validated_data):
        base = validated_data.get("slug") or validated_data.get("title") or "product"
        validated_data["slug"] = _unique_slug_for(
            Product, base, self.instance.pk if self.instance else None
        )
        return validated_data

    @transaction.atomic
    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        validated_data = self._ensure_slug(validated_data)
        product = Product.objects.create(**validated_data)

        # Validate each nested variant against the newly created product. This
        # catches cross-variant business rules (e.g. duplicate size+colour) that
        # cannot be known before the product exists. Any error raises, rolling
        # back the whole atomic block so no partial product/variants persist.
        variant_errors = []
        for variant_data in variants_data:
            variant = ProductVariant(product=product, **variant_data)
            try:
                variant.full_clean()
            except DjangoValidationError as exc:
                if hasattr(exc, "message_dict"):
                    variant_errors.append(exc.message_dict)
                else:
                    variant_errors.append({"non_field_errors": exc.messages})
                continue
            variant.save()

        if variant_errors:
            raise ValidationError({"variants": variant_errors})
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        # Nested variants are managed through the dedicated variant endpoints on
        # update to avoid destructive mass-replacement; only scalar fields change here.
        validated_data.pop("variants", None)
        if not validated_data.get("slug"):
            validated_data.pop("slug", None)
        else:
            validated_data = self._ensure_slug(validated_data)
        return super().update(instance, validated_data)
