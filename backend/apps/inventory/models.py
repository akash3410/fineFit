"""
Inventory domain models for the FineFit E-Commerce platform.

Design Principles:
------------------
1. Source of Truth:
   ``ProductVariant`` deliberately carries no stock fields. Stock levels are
   strictly owned by ``StockRecord`` via a one-to-one relationship.
2. Separation of Physical and Committed Stock:
   - ``quantity_on_hand``: Physical units physically present in inventory.
   - ``quantity_reserved``: Units allocated/reserved for active orders or carts.
   - ``available_quantity``: Derived consistently as max(0, quantity_on_hand - quantity_reserved).
3. Concurrency & Integrity:
   Check constraints in the database guarantee nonnegative stock and prevent
   reserved stock from exceeding on-hand stock.
4. Protected Audit Trail:
   Every alteration to stock or reservations records an immutable ``StockMovement``
   log entry detailing the delta, reason, timestamp, and actor. StockMovement
   instances cannot be modified or deleted via ordinary staff workflows.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class MovementReason(models.TextChoices):
    """Business reasons for inventory stock and reservation movements."""

    INITIAL_STOCK = "INITIAL_STOCK", _("Initial Stock / Seeding")
    PURCHASE_RECEIPT = "PURCHASE_RECEIPT", _("Purchase Receipt / Stock In")
    CORRECTION = "CORRECTION", _("Manual Inventory Correction")
    ORDER_CHECKOUT = "ORDER_CHECKOUT", _("Order Checkout / Sale")
    ORDER_CANCELLED = "ORDER_CANCELLED", _("Order Cancellation / Return to Stock")
    DAMAGE = "DAMAGE", _("Damaged / Defective Stock Written Off")
    RESERVATION = "RESERVATION", _("Stock Reservation")
    RESERVATION_RELEASE = "RESERVATION_RELEASE", _("Reservation Release")
    RETURN = "RETURN", _("Customer Return")


class StockRecordQuerySet(models.QuerySet):
    """QuerySet helpers for stock records."""

    def in_stock(self):
        """Filter records where available quantity is strictly positive."""
        return self.filter(quantity_on_hand__gt=models.F("quantity_reserved"))

    def low_stock(self):
        """Filter records where available quantity is at or below threshold and > 0."""
        return self.filter(
            quantity_on_hand__gt=models.F("quantity_reserved"),
            quantity_on_hand__lte=models.F("quantity_reserved") + models.F("low_stock_threshold"),
        )

    def out_of_stock(self):
        """Filter records with zero or exhausted available quantity."""
        return self.filter(quantity_on_hand__lte=models.F("quantity_reserved"))


class StockRecord(models.Model):
    """
    Inventory balance record linked one-to-one with a ProductVariant.

    Primary key is BigAutoField per ARCHITECTURE.md §2.3.
    """

    variant = models.OneToOneField(
        "catalog.ProductVariant",
        verbose_name=_("product variant"),
        on_delete=models.CASCADE,
        related_name="stock_record",
        help_text=_("Product variant this inventory balance belongs to."),
    )
    quantity_on_hand = models.PositiveIntegerField(
        _("quantity on hand"),
        default=0,
        help_text=_("Total physical stock present in inventory."),
    )
    quantity_reserved = models.PositiveIntegerField(
        _("quantity reserved"),
        default=0,
        help_text=_("Stock committed to active orders or reservations."),
    )
    low_stock_threshold = models.PositiveIntegerField(
        _("low stock threshold"),
        default=5,
        help_text=_("Threshold below which stock is flagged as low inventory."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = StockRecordQuerySet.as_manager()

    class Meta:
        verbose_name = _("stock record")
        verbose_name_plural = _("stock records")
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_on_hand__gte=0),
                name="stock_qty_on_hand_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__gte=0),
                name="stock_qty_reserved_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__lte=models.F("quantity_on_hand")),
                name="stock_reserved_lte_on_hand",
            ),
            models.CheckConstraint(
                condition=models.Q(low_stock_threshold__gte=0),
                name="stock_low_threshold_gte_0",
            ),
        ]

    def __str__(self) -> str:
        sku = self.variant.sku if self.variant_id else "Unassigned"
        return f"StockRecord({sku}: on_hand={self.quantity_on_hand}, reserved={self.quantity_reserved}, available={self.available_quantity})"

    @property
    def available_quantity(self) -> int:
        """Units immediately available for purchase or reservation."""
        return max(0, self.quantity_on_hand - self.quantity_reserved)

    @property
    def quantity_available(self) -> int:
        """Alias for available_quantity."""
        return self.available_quantity

    @property
    def quantity(self) -> int:
        """
        Quantity on hand representation.
        Provided for compatibility with ARCHITECTURE.md §2.3.
        """
        return self.quantity_on_hand

    @property
    def is_in_stock(self) -> bool:
        """True if at least one unit is available for purchase."""
        return self.available_quantity > 0

    @property
    def is_low_stock(self) -> bool:
        """True if available stock is positive but at or below the low stock threshold."""
        return 0 < self.available_quantity <= self.low_stock_threshold

    def clean(self):
        super().clean()
        if self.quantity_on_hand < 0:
            raise ValidationError(
                {"quantity_on_hand": _("Quantity on hand cannot be negative.")}
            )
        if self.quantity_reserved < 0:
            raise ValidationError(
                {"quantity_reserved": _("Quantity reserved cannot be negative.")}
            )
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValidationError(
                {"quantity_reserved": _("Quantity reserved cannot exceed quantity on hand.")}
            )
        if self.low_stock_threshold < 0:
            raise ValidationError(
                {"low_stock_threshold": _("Low stock threshold cannot be negative.")}
            )


class StockMovement(models.Model):
    """
    Immutable audit trail recording every inventory alteration or reservation event.

    Protected against accidental modification or deletion by staff workflows.
    """

    stock_record = models.ForeignKey(
        StockRecord,
        verbose_name=_("stock record"),
        on_delete=models.PROTECT,
        related_name="movements",
        help_text=_("Stock record modified by this movement."),
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        verbose_name=_("product variant"),
        on_delete=models.PROTECT,
        related_name="stock_movements",
        help_text=_("Product variant affected by this movement."),
    )
    quantity_delta = models.IntegerField(
        _("quantity delta"),
        default=0,
        help_text=_("Net change to quantity on hand (+/-). 0 for pure reservations."),
    )
    reserved_delta = models.IntegerField(
        _("reserved delta"),
        default=0,
        help_text=_("Net change to quantity reserved (+/-)."),
    )
    reason = models.CharField(
        _("reason"),
        max_length=64,
        choices=MovementReason.choices,
        help_text=_("Operational reason for the movement."),
    )
    notes = models.TextField(
        _("operational notes"),
        blank=True,
        help_text=_("Context or justification for the adjustment."),
    )
    reference_id = models.CharField(
        _("reference identifier"),
        max_length=128,
        blank=True,
        help_text=_("External reference such as order ID, PO number, or return token."),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("responsible actor"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text=_("User or system principal who initiated the movement."),
    )
    created_at = models.DateTimeField(
        _("created at"),
        auto_now_add=True,
        db_index=True,
        help_text=_("Timestamp when the movement occurred."),
    )

    class Meta:
        verbose_name = _("stock movement")
        verbose_name_plural = _("stock movements")
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["variant", "-created_at"], name="movement_variant_time_idx"),
            models.Index(fields=["reason", "-created_at"], name="movement_reason_time_idx"),
        ]

    def __str__(self) -> str:
        sku = self.variant.sku if self.variant_id else "Unknown"
        ref = f", ref={self.reference_id}" if self.reference_id else ""
        return (
            f"Movement({sku}: delta={self.quantity_delta:+d}, "
            f"reserved_delta={self.reserved_delta:+d}, reason={self.reason}{ref})"
        )

    def save(self, *args, **kwargs):
        """
        Enforce audit log immutability: once persisted, movement rows cannot be modified.
        """
        if self.pk is not None:
            raise ValidationError(
                _("StockMovement records are immutable audit logs and cannot be updated.")
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Enforce audit log immutability: movement rows cannot be deleted.
        """
        raise ValidationError(
            _("StockMovement records are immutable audit logs and cannot be deleted.")
        )
