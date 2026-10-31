"""
Cart domain models for the FineFit E-Commerce platform.

Design principles
-----------------
1. Dual-mode ownership (ADR-005): a ``Cart`` belongs to exactly ONE owner —
   either an authenticated ``CustomUser`` or a guest Django session key —
   never both and never neither. This is enforced by a database CHECK
   constraint plus partial unique indexes, so ownership integrity cannot be
   violated even by non-Django writers.
2. No denormalized catalog data: ``CartItem`` stores only the variant FK and
   quantity. Prices, SKUs, titles and stock figures are always computed
   server-side from the trusted catalog/inventory rows at read time. Clients
   can never inject prices or quantities of stock.
3. No stock reservation: per ADR-010 (Option B, accepted), the cart NEVER
   reserves or decrements inventory. ``apps.inventory.StockRecord`` /
   ``StockMovement`` are only read (advisory availability checks); the source
   of truth is re-validated at checkout (Phase 4B).
4. Future returns/exchange compatibility: cart rows are throwaway staging
   data (no financial snapshot). Immutable purchase snapshots live on future
   ``apps.orders.OrderItem`` rows, so cart design imposes no constraints on
   future partial-return / exchange workflows.

Primary keys (per docs/ARCHITECTURE.md conventions):
   - ``Cart``     -> UUID primary key (enumeration-sensitive commerce entity)
   - ``CartItem`` -> BigAutoField (child row owned by a cart UUID)
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class CartQuerySet(models.QuerySet):
    """Queryset helpers for cart ownership lookups."""

    def for_user(self, user):
        """The active cart belonging to an authenticated user."""
        return self.filter(user=user, session_key__isnull=True)

    def for_guest_session(self, session_key):
        """The active cart belonging to a guest session key."""
        return self.filter(user__isnull=True, session_key=session_key)


class Cart(models.Model):
    """
    A shopping cart owned by either an authenticated customer or a guest session.

    Exactly one of ``user`` / ``session_key`` is set:
      - authenticated customer cart: ``user`` set, ``session_key`` null/empty
      - guest session cart: ``session_key`` set, ``user`` null
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this cart."),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("authenticated user"),
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
        help_text=_("Customer who owns this cart, if authenticated."),
    )
    session_key = models.CharField(
        _("guest session key"),
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Django session key owning this cart, if unauthenticated."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = CartQuerySet.as_manager()

    class Meta:
        verbose_name = _("shopping cart")
        verbose_name_plural = _("shopping carts")
        ordering = ["-updated_at"]
        constraints = [
            # Exactly one owner: user XOR (session_key set and non-empty).
            # Built from tuple children to mirror the applied migration's
            # serialized-checksum-stable deconstruction.
            models.CheckConstraint(
                condition=models.Q(
                    models.Q(("user__isnull", False), ("session_key__isnull", True)),
                    models.Q(
                        ("user__isnull", True),
                        ("session_key__isnull", False),
                        models.Q(("session_key", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="cart_single_owner_constraint",
            ),
            # One active user cart per customer.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(user__isnull=False),
                name="unique_active_user_cart",
            ),
            # One active guest cart per session.
            models.UniqueConstraint(
                fields=["session_key"],
                condition=models.Q(session_key__isnull=False),
                name="unique_active_session_cart",
            ),
        ]

    def __str__(self) -> str:
        if self.user_id:
            owner = getattr(self.user, "email", None) or f"user#{self.user_id}"
            return f"Cart(user={owner})"
        return f"Cart(session={self.session_key[:8]}...)"

    # -- Ownership integrity (application-layer backstop for the DB CHECK) ---
    def clean(self):
        super().clean()
        has_user = self.user_id is not None
        has_session = bool(self.session_key)
        if has_user and has_session:
            raise ValidationError(
                _("A cart cannot belong to both an authenticated user and a guest session.")
            )
        if not has_user and not has_session:
            raise ValidationError(_("A cart must belong to a user or a guest session."))

    # -- Derived aggregates (composed from trusted relations only) ------------
    @property
    def total_quantity(self) -> int:
        """Total number of units currently staged in this cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        """Current cart subtotal: sum of line totals in Decimal arithmetic."""
        return sum(
            (item.line_total for item in self.items.all()), start=Decimal("0.00")
        )

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()

    @property
    def has_stock_conflicts(self) -> bool:
        """True when any staged quantity exceeds the currently available stock."""
        return any(item.has_sufficient_stock is False for item in self.items.all())


class CartItem(models.Model):
    """
    A variant staged in a cart with a strictly positive quantity.

    Deliberately stores NO catalog denormalization (title, price, SKU). The
    current unit price is always derived from the trusted server-side variant
    (``variant.effective_price``) at serialization time, so cart totals can
    never be tampered with or go stale silently.
    """

    id = models.BigAutoField(
        primary_key=True,
    )
    cart = models.ForeignKey(
        Cart,
        verbose_name=_("shopping cart"),
        on_delete=models.CASCADE,
        related_name="items",
        help_text=_("Shopping cart containing this item."),
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        verbose_name=_("product variant"),
        on_delete=models.CASCADE,
        related_name="cart_items",
        help_text=_("Catalog product variant selected by the customer."),
    )
    quantity = models.PositiveIntegerField(
        _("quantity"),
        default=1,
        help_text=_("Quantity of the variant in the cart. Must be >= 1."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("cart item")
        verbose_name_plural = _("cart items")
        ordering = ["created_at"]
        constraints = [
            # One line per variant per cart; re-adding the same variant merges.
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_cart_variant",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="cart_item_quantity_gt_0",
            ),
        ]

    def __str__(self) -> str:
        sku = self.variant.sku if self.variant_id else "unknown"
        return f"CartItem({sku} x{self.quantity})"

    def clean(self):
        super().clean()
        if self.quantity < 1:
            raise ValidationError(
                {"quantity": _("Quantity must be at least 1.")}
            )

    # -- Trusted, server-side derived values ----------------------------------
    @property
    def unit_price(self):
        """
        Current trusted unit price for the variant (never client-supplied).
        Normalised to Decimal so line arithmetic is always exact.
        """
        if not self.variant_id:
            return None
        price = self.variant.effective_price
        if price is None:
            return None
        return Decimal(str(price))

    @property
    def line_total(self):
        """Current line total in Decimal arithmetic: unit_price * quantity."""
        price = self.unit_price
        if price is None:
            return None
        return price * self.quantity

    @property
    def available_quantity(self) -> int:
        """
        Current sellable units for this variant, derived from the inventory
        source of truth. A missing StockRecord is treated as unavailable (0).
        Read-only with respect to inventory: never mutates stock.
        """
        if not self.variant_id:
            return 0
        stock_record = getattr(self.variant, "stock_record", None)
        return stock_record.available_quantity if stock_record else 0

    @property
    def has_sufficient_stock(self) -> bool:
        """True if the staged quantity is currently available."""
        return self.quantity <= self.available_quantity

    @property
    def is_available(self) -> bool:
        """True if the variant is currently purchasable (any unit available)."""
        return self.available_quantity > 0
