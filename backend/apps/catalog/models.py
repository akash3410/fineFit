"""
Catalog domain models for the FineFit E-Commerce platform.

Domain boundary note — Inventory
--------------------------------
``ProductVariant`` deliberately carries NO stock quantity / inventory fields.
Stock levels are owned by the separate ``apps.inventory`` application
(``StockRecord``), which references a variant via a one-to-one relationship
through the reverse accessor ``variant.stock_record``. This keeps stock
mutation, reservation, and atomic locking concerns isolated from the read-mostly
catalog domain. Catalog exposes only variant *attributes* (size, colour, price).

Primary key strategy (per docs/ARCHITECTURE.md §2.2):
  - ``Category``       -> BigAutoField (public taxonomy, non-sensitive)
  - ``Product``        -> UUID          (enumeration-sensitive commerce entity)
  - ``ProductVariant`` -> UUID          (enumeration-sensitive commerce entity)
  - ``ProductImage``   -> BigAutoField  (child row tied to a product)
"""

import os
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Validation constants (single source of truth, shared with serializers)
# ---------------------------------------------------------------------------

#: Hex colour swatch validator, e.g. ``#1F2937``.
validate_color_code = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message=_("Colour code must be a hex value in the form '#RRGGBB'."),
)

#: Upper bound (inclusive) for a price stored with 2 decimal places.
MAX_PRICE = 99999999.99


def product_image_upload_path(instance, filename: str) -> str:
    """
    Deterministic, collision-resistant upload path for product images.

    Files are stored under ``catalog/products/<product_uuid>/<uuid><ext>``.
    A random UUID suffix avoids filename collisions and accidental overwrites
    while keeping all assets for a product grouped together.
    """
    extension = os.path.splitext(filename)[1].lower()
    return f"catalog/products/{instance.product_id}/{uuid.uuid4().hex}{extension}"


class CategoryQuerySet(models.QuerySet):
    """Queryset helpers for the category tree."""

    def active(self):
        return self.filter(is_active=True)


class Category(models.Model):
    """
    Hierarchical product category (a simple tree via a self-referential parent).

    ``slug`` is globally unique so category URLs are stable and human readable
    (``/catalog/{slug}/``) without needing the parent path.
    """

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        help_text=_("Globally unique URL identifier for this category."),
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("parent category"),
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
        help_text=_("Optional parent category; empty for a top-level category."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive categories are hidden from the public storefront."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(id=models.F("parent")),
                name="category_parent_not_self",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    # -- Tree helpers -------------------------------------------------------
    def get_ancestors(self) -> list["Category"]:
        """
        Return ancestor categories from the immediate parent upward.

        Raises ``ValidationError`` if a cycle is detected (defensive; the
        ``clean()`` guard prevents cycles from being saved in the first place).
        """
        ancestors: list[Category] = []
        seen: set[int] = set()
        current = self.parent
        while current is not None:
            if current.pk in seen:
                raise ValidationError({"parent": _("Category hierarchy contains a cycle.")})
            seen.add(current.pk)
            ancestors.append(current)
            current = current.parent
        return ancestors

    def clean(self):
        super().clean()
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": _("A category cannot be its own parent.")})
        # Prevent introducing a cycle: a descendant cannot become an ancestor.
        if self.pk and self.parent_id:
            for ancestor in self.parent.get_ancestors():
                if ancestor.pk == self.pk:
                    raise ValidationError(
                        {"parent": _("A category cannot be moved under one of its own descendants.")}
                    )


class ProductQuerySet(models.QuerySet):
    """Queryset helpers enforcing the public visibility rules."""

    def published(self):
        """Products that are publicly visible (published under an active category)."""
        return self.filter(is_published=True, category__is_active=True)


class Product(models.Model):
    """
    A sellable fashion item (e.g. "Aurora Wool Overcoat").

    Variants (size/colour combinations) hang off the product. Publication is
    explicit: only ``is_published=True`` products under an active category are
    exposed on public endpoints.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this product across the platform."),
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("category"),
        on_delete=models.PROTECT,
        related_name="products",
    )
    title = models.CharField(_("title"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        help_text=_("Globally unique URL identifier for this product."),
    )
    description = models.TextField(_("description"), blank=True)
    base_price = models.DecimalField(
        _("base price"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_("Base retail price; a variant may override this."),
    )
    is_published = models.BooleanField(
        _("published"),
        default=False,
        help_text=_("Draft (unpublished) products are never exposed publicly."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["is_published", "created_at"],
                name="product_pub_created_idx",
            ),
            models.Index(
                fields=["is_published", "base_price"],
                name="product_pub_price_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(base_price__gte=0),
                name="product_base_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class ProductVariant(models.Model):
    """
    A specific size/colour combination of a product, identified by a unique SKU.

    Inventory boundary: NO stock quantity lives here. Stock is managed by
    ``apps.inventory.StockRecord`` (one-to-one via ``variant.stock_record``).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this variant across the platform."),
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("product"),
        on_delete=models.CASCADE,
        related_name="variants",
    )
    sku = models.CharField(
        _("SKU"),
        max_length=64,
        unique=True,
        help_text=_("Stock keeping unit; unique across the entire catalog."),
    )
    size = models.CharField(
        _("size"),
        max_length=32,
        blank=True,
        help_text=_("e.g. XS, S, M, L, XL."),
    )
    color_name = models.CharField(
        _("colour name"),
        max_length=64,
        blank=True,
        help_text=_("e.g. Midnight Black, Emerald Green."),
    )
    color_code = models.CharField(
        _("colour code"),
        max_length=7,
        blank=True,
        validators=[validate_color_code],
        help_text=_("Hex swatch, e.g. '#1F2937'."),
    )
    price_override = models.DecimalField(
        _("price override"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Optional variant-specific price; falls back to the product base price."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive variants are hidden from the public storefront."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("product variant")
        verbose_name_plural = _("product variants")
        ordering = ["size", "color_name", "sku"]
        indexes = [
            models.Index(
                fields=["product", "is_active"],
                name="variant_product_active_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_override__isnull=True)
                | models.Q(price_override__gte=0),
                name="variant_price_override_non_negative",
            ),
        ]

    def __str__(self) -> str:
        parts = [self.product.title if self.product_id else ""]
        if self.size:
            parts.append(self.size)
        if self.color_name:
            parts.append(self.color_name)
        return " / ".join(p for p in parts if p) or self.sku

    @property
    def effective_price(self):
        """Variant price: the override if set, otherwise the product base price."""
        if self.price_override is not None:
            return self.price_override
        return self.product.base_price if self.product_id else None

    def clean(self):
        super().clean()
        # Business rule: a product must not contain two variants with the same
        # size + colour name. Enforced in the application layer rather than a DB
        # constraint because blank size/colour combinations are legitimate (a
        # product may ship a single generic variant), and a partial unique index
        # would forbid more than one such generic variant per product. SKU
        # uniqueness remains enforced at the database level.
        if self.product_id:
            duplicate = (
                ProductVariant.objects.filter(
                    product_id=self.product_id,
                    size=self.size,
                    color_name=self.color_name,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicate:
                raise ValidationError(
                    {
                        "size": _(
                            "This product already has a variant with the same size and colour."
                        )
                    }
                )


class ProductImage(models.Model):
    """
    An image belonging to a product, optionally tied to a specific variant.

    Ordering is deterministic (``display_order`` then ``id``). Exactly one image
    per product may be flagged ``is_primary`` (enforced by a partial unique
    constraint at the database level).
    """

    product = models.ForeignKey(
        Product,
        verbose_name=_("product"),
        on_delete=models.CASCADE,
        related_name="images",
    )
    variant = models.ForeignKey(
        ProductVariant,
        verbose_name=_("variant"),
        on_delete=models.SET_NULL,
        related_name="images",
        null=True,
        blank=True,
        help_text=_("Optional variant this image specifically depicts."),
    )
    image = models.ImageField(
        _("image"),
        upload_to=product_image_upload_path,
    )
    alt_text = models.CharField(
        _("alternative text"),
        max_length=150,
        blank=True,
        help_text=_("Accessible description of the image."),
    )
    display_order = models.PositiveIntegerField(
        _("display order"),
        default=0,
        help_text=_("Lower numbers are shown first."),
    )
    is_primary = models.BooleanField(
        _("primary"),
        default=False,
        help_text=_("The single primary image shown on list/detail views."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("product image")
        verbose_name_plural = _("product images")
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_primary=True),
                name="unique_primary_image_per_product",
            ),
        ]

    def __str__(self) -> str:
        return f"Image for {self.product_id} ({'primary' if self.is_primary else 'secondary'})"

    def clean(self):
        super().clean()
        # Cross-object integrity: a variant-linked image must belong to the same
        # product as its variant. Prevents mismatched product/variant/image rows.
        if self.variant_id and self.product_id:
            if self.variant.product_id != self.product_id:
                raise ValidationError(
                    {"variant": _("The selected variant does not belong to this product.")}
                )
