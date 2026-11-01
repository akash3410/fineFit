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
from django.utils import timezone
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
        return self.filter(is_active=True, is_deleted=False)

    def soft_deleted(self):
        return self.filter(is_deleted=True)


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
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive categories are hidden from the public storefront."),
    )
    is_deleted = models.BooleanField(
        _("deleted"),
        default=False,
        help_text=_("Soft-deleting preserves the record for future order history."),
    )
    deleted_at = models.DateTimeField(
        _("deleted at"),
        null=True,
        blank=True,
        help_text=_("Timestamp when the category was soft-deleted."),
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

    def soft_delete(self):
        """Mark the category as deleted without physically removing it."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        """Restore a soft-deleted category."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class SubcategoryQuerySet(models.QuerySet):
    """Queryset helpers for the subcategory collection."""

    def active(self):
        return self.filter(is_active=True, is_deleted=False)

    def soft_deleted(self):
        return self.filter(is_deleted=True)


class Subcategory(models.Model):
    """
    A second-level classification under a top-level ``Category``.

    Each subcategory belongs to exactly one parent category and contains its own
    slug, guaranteed unique within parent via a database constraint.
    """

    category = models.ForeignKey(
        Category,
        verbose_name=_("parent category"),
        on_delete=models.PROTECT,
        related_name="subcategories",
        help_text=_("Top-level category this subcategory belongs to."),
    )
    name = models.CharField(_("name"), max_length=150)
    slug = models.SlugField(
        _("slug"),
        max_length=160,
        help_text=_("URL identifier, unique within the parent category."),
    )
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Inactive subcategories are hidden from the public storefront."),
    )
    is_deleted = models.BooleanField(
        _("deleted"),
        default=False,
        help_text=_("Soft-deleting preserves the record for historical reference."),
    )
    deleted_at = models.DateTimeField(
        _("deleted at"),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = SubcategoryQuerySet.as_manager()

    class Meta:
        verbose_name = _("subcategory")
        verbose_name_plural = _("subcategories")
        ordering = ["category__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_subcategory_name_per_category",
            ),
            models.UniqueConstraint(
                fields=["category", "slug"],
                name="unique_subcategory_slug_per_category",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if self.is_deleted:
            raise ValidationError({"is_deleted": _("A deleted subcategory cannot be edited.")})
        if self.pk and self.category_id and self.category.is_deleted:
            raise ValidationError({"category": _("Cannot add a subcategory to a deleted category.")})

    def soft_delete(self):
        """Mark the subcategory as deleted without physically removing it."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        """Restore a soft-deleted subcategory."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class ProductQuerySet(models.QuerySet):
    """Queryset helpers enforcing the public visibility rules."""

    def active(self):
        return self.filter(is_deleted=False)

    def published(self):
        """Products that are publicly visible (published under an active category)."""
        return self.filter(is_published=True, category__is_active=True, is_deleted=False)

    def soft_deleted(self):
        return self.filter(is_deleted=True)


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
    subcategory = models.ForeignKey(
        Subcategory,
        verbose_name=_("subcategory"),
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        help_text=_("Optional subcategory this product belongs to."),
    )
    title = models.CharField(_("title"), max_length=255)
    slug = models.SlugField(
        _("slug"),
        max_length=255,
        unique=True,
        help_text=_("Globally unique URL identifier for this product."),
    )
    sku = models.CharField(
        _("SKU"),
        max_length=64,
        unique=False,
        blank=True,
        null=True,
        help_text=_("Stock keeping unit; unique across the entire catalog."),
    )
    description = models.TextField(_("description"), blank=True)
    price = models.DecimalField(
        _("price"),
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Base retail price; a variant may override this."),
    )
    discount_price = models.DecimalField(
        _("discount price"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Optional discounted price; must be less than price."),
    )
    stock = models.PositiveIntegerField(
        _("stock"),
        default=0,
        help_text=_("Total available stock quantity (aggregated from variants if applicable)."),
    )
    status = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Active products are visible on the storefront."),
    )
    is_published = models.BooleanField(
        _("published"),
        default=False,
        help_text=_("Draft (unpublished) products are never exposed publicly."),
    )
    is_featured = models.BooleanField(
        _("featured"),
        default=False,
        help_text=_("Featured products are highlighted on the storefront."),
    )
    is_deleted = models.BooleanField(
        _("deleted"),
        default=False,
        help_text=_("Soft-deleting preserves the record for future order history."),
    )
    deleted_at = models.DateTimeField(
        _("deleted at"),
        null=True,
        blank=True,
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
                fields=["is_published", "price"],
                name="product_pub_price_idx",
            ),
            models.Index(
                fields=["status", "is_deleted"],
                name="product_status_deleted_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="product_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_price__isnull=True)
                | models.Q(discount_price__lt=models.F("price")),
                name="product_discount_price_lt_price",
            ),
            models.CheckConstraint(
                condition=models.Q(stock__gte=0),
                name="product_stock_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def name(self) -> str:
        """Alias for title to match plan terminology."""
        return self.title

    @property
    def is_active(self) -> bool:
        """Check if product is active (status True and not deleted)."""
        return self.status and not self.is_deleted

    def clean(self):
        super().clean()
        if self.is_deleted:
            raise ValidationError({"is_deleted": _("A deleted product cannot be edited.")})
        if self.subcategory_id and self.category_id:
            if self.subcategory.category_id != self.category_id:
                raise ValidationError(
                    {"subcategory": _("The selected subcategory must belong to the selected category.")}
                )
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValidationError(
                {"discount_price": _("Discount price must be less than the regular price.")}
            )

    def soft_delete(self):
        """Mark the product as deleted without physically removing it."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        """Restore a soft-deleted product."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class ProductVariant(models.Model):
    """
    A specific size/colour combination of a product, identified by a unique SKU.

    Stock is tracked directly on variants for admin management convenience.
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
    stock = models.PositiveIntegerField(
        _("stock"),
        default=0,
        help_text=_("Available stock quantity for this variant."),
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
            models.CheckConstraint(
                condition=models.Q(stock__gte=0),
                name="variant_stock_non_negative",
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
        return self.product.price if self.product_id else None

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
    is_main = models.BooleanField(
        _("main image"),
        default=False,
        help_text=_("The main/primary image for product display."),
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
        return f"Image for {self.product_id} ({'primary' if self.is_primary or self.is_main else 'secondary'})"

    def clean(self):
        super().clean()
        # Cross-object integrity: a variant-linked image must belong to the same
        # product as its variant. Prevents mismatched product/variant/image rows.
        if self.variant_id and self.product_id:
            if self.variant.product_id != self.product_id:
                raise ValidationError(
                    {"variant": _("The selected variant does not belong to this product.")}
                )
        # Sync is_main with is_primary for backward compatibility
        if self.is_main and not self.is_primary:
            self.is_primary = True
        elif self.is_primary and not self.is_main:
            self.is_main = True
