"""Orders domain models for the FineFit E-Commerce platform.

Design principles
-----------------
1. Immutable purchase snapshots: ``OrderItem`` copies the product title, SKU,
   size, colour and unit price at the moment of purchase. Later catalog edits
   (price changes, renamed products, deleted variants) never rewrite history.
2. Dual-mode ownership (mirrors ``apps.cart``): an order belongs to exactly one
   owner — an authenticated ``CustomUser`` or a guest Django session key.
   Customer-facing lookups always filter by that owner server-side; an order
   number alone never grants access.
3. Cash on delivery only for this phase: no card data, no payment tokens and
   no gateway state are stored anywhere in the platform.
4. Money is Decimal end to end. ``total`` is always ``subtotal + shipping_fee``
   and is computed server-side from trusted variant prices.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class OrderStatus(models.TextChoices):
    """Lifecycle of an order from submission to fulfilment."""

    PENDING = "PENDING", _("Pending")
    CONFIRMED = "CONFIRMED", _("Confirmed")
    PROCESSING = "PROCESSING", _("Processing")
    SHIPPED = "SHIPPED", _("Shipped")
    DELIVERED = "DELIVERED", _("Delivered")
    CANCELLED = "CANCELLED", _("Cancelled")
    RETURNED = "RETURNED", _("Returned")


class PaymentMethod(models.TextChoices):
    """Supported settlement methods. Cash on delivery is the only one for now."""

    COD = "COD", _("Cash on Delivery")


class OrderQuerySet(models.QuerySet):
    """Ownership-scoped lookups for orders."""

    def for_customer(self, user):
        """Orders belonging to an authenticated customer."""
        return self.filter(user=user)

    def for_guest_session(self, session_key):
        """Orders placed by a guest session (never owner-less)."""
        return self.filter(user__isnull=True, session_key=session_key)


class Order(models.Model):
    """A placed order with a frozen price snapshot and a delivery address."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this order."),
    )
    order_number = models.CharField(
        _("order number"),
        max_length=32,
        unique=True,
        editable=False,
        help_text=_("Customer-facing reference, e.g. ORD-2026-8F3K2A."),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("customer"),
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
        help_text=_("Authenticated customer who placed the order, if any."),
    )
    session_key = models.CharField(
        _("guest session key"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_("Django session key owning the order, when placed as a guest."),
    )
    customer_name = models.CharField(_("customer name"), max_length=255)
    customer_email = models.EmailField(_("email"), blank=True)
    customer_phone = models.CharField(_("phone"), max_length=20)
    shipping_address = models.JSONField(
        _("shipping address"),
        help_text=_(
            "Address snapshot: address_line1, address_line2, city, area, "
            "postal_code, country."
        ),
    )
    notes = models.TextField(_("delivery notes"), blank=True)
    payment_method = models.CharField(
        _("payment method"),
        max_length=16,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    subtotal = models.DecimalField(
        _("subtotal"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    shipping_fee = models.DecimalField(
        _("shipping fee"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total = models.DecimalField(
        _("total"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = _("order")
        verbose_name_plural = _("orders")
        ordering = ["-created_at"]
        constraints = [
            # Exactly one owner: a customer XOR a non-empty guest session key.
            models.CheckConstraint(
                condition=models.Q(
                    models.Q(("user__isnull", False), ("session_key", "")),
                    models.Q(("user__isnull", True), ("session_key__isnull", False))
                    & ~models.Q(("session_key", "")),
                    _connector="OR",
                ),
                name="order_single_owner_constraint",
            ),
        ]

    def __str__(self) -> str:
        return f"Order({self.order_number}, {self.status}, total={self.total})"

    def clean(self):
        super().clean()
        if self.user_id and self.session_key:
            raise ValidationError(
                _("An order cannot belong to both a customer and a guest session.")
            )
        if not self.user_id and not self.session_key:
            raise ValidationError(
                _("An order must belong to a customer or a guest session.")
            )
        if self.subtotal + self.shipping_fee != self.total:
            raise ValidationError(
                _("Total must equal subtotal plus shipping fee.")
            )

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number() -> str:
        """Human-readable, non-sequential reference (e.g. ORD-2026-8F3K2A)."""
        year = timezone.now().year
        for _ in range(5):
            candidate = f"ORD-{year}-{uuid.uuid4().hex[:6].upper()}"
            if not Order.objects.filter(order_number=candidate).exists():
                return candidate
        # Astronomically unlikely; fall back to a full UUID for guaranteed uniqueness.
        return f"ORD-{year}-{uuid.uuid4().hex.upper()}"

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def is_cash_on_delivery(self) -> bool:
        return self.payment_method == PaymentMethod.COD


class OrderItem(models.Model):
    """A purchased line with an immutable snapshot of what was bought."""

    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        verbose_name=_("order"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        verbose_name=_("product variant"),
        on_delete=models.SET_NULL,
        related_name="order_items",
        null=True,
        blank=True,
        help_text=_("Variant purchased; may be removed from the catalog later."),
    )
    product_title = models.CharField(_("product title"), max_length=255)
    variant_sku = models.CharField(_("SKU"), max_length=64)
    size = models.CharField(_("size"), max_length=32, blank=True)
    color_name = models.CharField(_("colour name"), max_length=64, blank=True)
    unit_price = models.DecimalField(_("unit price"), max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(_("quantity"))
    returned_quantity = models.PositiveIntegerField(
        _("returned quantity"),
        default=0,
        help_text=_("Units already returned and put back into stock."),
    )
    line_total = models.DecimalField(_("line total"), max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("order item")
        verbose_name_plural = _("order items")
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_gt_0",
            ),
            # A line can never return more units than it sold.
            models.CheckConstraint(
                condition=models.Q(returned_quantity__lte=models.F("quantity")),
                name="order_item_returned_lte_quantity",
            ),
        ]

    def __str__(self) -> str:
        return f"OrderItem({self.variant_sku} x{self.quantity})"

    @property
    def remaining_quantity(self) -> int:
        """Units still eligible for a return."""
        return max(self.quantity - self.returned_quantity, 0)

    @property
    def is_fully_returned(self) -> bool:
        return self.returned_quantity >= self.quantity


class OrderStatusChange(models.Model):
    """Audit trail of who moved an order between statuses, and when.

    Partial returns do not change the order status, so they are recorded with
    ``previous_status == new_status`` and a note describing the returned units.
    ``changed_by`` is null when the change was made by the system (for example a
    guest's own checkout) or by a staff account that has since been deleted.
    """

    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        verbose_name=_("order"),
        on_delete=models.CASCADE,
        related_name="status_changes",
    )
    previous_status = models.CharField(
        _("previous status"), max_length=16, choices=OrderStatus.choices, blank=True
    )
    new_status = models.CharField(
        _("new status"), max_length=16, choices=OrderStatus.choices
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("changed by"),
        on_delete=models.SET_NULL,
        related_name="order_status_changes",
        null=True,
        blank=True,
        help_text=_("Staff account that made the change, if any."),
    )
    note = models.CharField(_("note"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("order status change")
        verbose_name_plural = _("order status changes")
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return (
            f"OrderStatusChange({self.order.order_number}, "
            f"{self.previous_status or 'NEW'} -> {self.new_status})"
        )

    @property
    def is_status_transition(self) -> bool:
        return self.previous_status != self.new_status


class ReturnRequestStatus(models.TextChoices):
    """Lifecycle of a customer-initiated return request."""

    REQUESTED = "REQUESTED", _("Requested")
    APPROVED = "APPROVED", _("Approved")
    DECLINED = "DECLINED", _("Declined")


class ReturnRequest(models.Model):
    """A customer's request to return units from a delivered order.

    A request is only intent: stock is never touched until staff approve it,
    because the units must physically come back first. Approval reuses
    ``OrderService.return_items()`` so restocking and the audit/ledger records
    are identical to a staff-recorded return.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this return request."),
    )
    order = models.ForeignKey(
        Order,
        verbose_name=_("order"),
        on_delete=models.CASCADE,
        related_name="return_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("requested by"),
        on_delete=models.SET_NULL,
        related_name="return_requests",
        null=True,
        blank=True,
        help_text=_(
            "Customer account that asked for the return; empty for guests."
        ),
    )
    reason = models.TextField(_("reason"), blank=True)
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=ReturnRequestStatus.choices,
        default=ReturnRequestStatus.REQUESTED,
        db_index=True,
    )
    staff_note = models.CharField(_("staff note"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("resolved by"),
        on_delete=models.SET_NULL,
        related_name="resolved_return_requests",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("return request")
        verbose_name_plural = _("return requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["order", "status"], name="return_req_order_status_idx"
            )
        ]

    def __str__(self) -> str:
        return f"ReturnRequest({self.order.order_number}, {self.status})"

    @property
    def is_open(self) -> bool:
        """True while the request is still waiting for staff review."""
        return self.status == ReturnRequestStatus.REQUESTED

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())


class ReturnRequestItem(models.Model):
    """Units of one order line a customer wants to return."""

    id = models.BigAutoField(primary_key=True)
    request = models.ForeignKey(
        ReturnRequest,
        verbose_name=_("request"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_item = models.ForeignKey(
        OrderItem,
        verbose_name=_("order item"),
        on_delete=models.CASCADE,
        related_name="return_request_items",
    )
    quantity = models.PositiveIntegerField(_("quantity"))

    class Meta:
        verbose_name = _("return request item")
        verbose_name_plural = _("return request items")
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="return_request_item_quantity_gt_0",
            )
        ]

    def __str__(self) -> str:
        return f"ReturnRequestItem({self.order_item.variant_sku} x{self.quantity})"
