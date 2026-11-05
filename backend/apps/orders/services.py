"""OrderService: transactional order placement.

Checkout is the only place where cart intent becomes a purchase. It runs in a
single ``transaction.atomic()`` block that:

1. re-validates every cart line against the trusted catalog (variant active,
   product published, product not deleted) and the inventory source of truth;
2. locks the ``StockRecord`` rows in a deterministic order (via
   ``StockService.lock_stock_records``) so concurrent checkouts cannot oversell;
3. writes the order and immutable line snapshots priced from the trusted
   variant prices — client-submitted prices or totals are never accepted;
4. deducts stock through ``StockService`` so every sale leaves an
   ``ORDER_CHECKOUT`` ledger movement;
5. clears the cart.

Cash on delivery is the only payment method: no card data or gateway state is
handled, and the order is created in ``PENDING`` awaiting staff confirmation.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cart.models import Cart
from apps.cart.services import CartService
from apps.inventory.models import MovementReason
from apps.inventory.services import StockService

from .exceptions import (
    EmptyCartError,
    OrderValidationError,
    UnavailableItemError,
)
from .models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusChange,
    PaymentMethod,
    ReturnRequest,
    ReturnRequestItem,
    ReturnRequestStatus,
)


# Statuses in which a delivered/confirmed sale can still be returned.
RETURNABLE_STATUSES = (
    OrderStatus.CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
)

# Statuses in which the *customer* may ask for a return. The goods have to be
# in their hands before a request makes sense; earlier statuses are a staff
# cancellation instead.
CUSTOMER_RETURNABLE_STATUSES = (OrderStatus.DELIVERED,)


class OrderService:
    """Service layer for order placement, status changes and returns."""

    @classmethod
    @transaction.atomic
    def place_order(
        cls,
        cart: Cart | None,
        *,
        customer_name: str,
        customer_phone: str,
        shipping_address: dict,
        customer_email: str = "",
        notes: str = "",
        payment_method: str = PaymentMethod.COD,
        user=None,
        session_key: str = "",
    ) -> Order:
        """Turn the owner's cart into a cash-on-delivery order.

        Raises:
            EmptyCartError: No cart, or a cart with no lines.
            OrderValidationError: Ownership mismatch or unsupported payment method.
            UnavailableItemError: A line is no longer purchasable at the
                requested quantity (stock or catalog availability changed).
            InsufficientStockError: Propagated from inventory if another
                checkout consumed the stock between validation and deduction.
        """
        cls._validate_owner(cart, user=user, session_key=session_key)
        if payment_method != PaymentMethod.COD:
            raise OrderValidationError("Only cash on delivery is available.")

        if cart is None:
            raise EmptyCartError("Your bag is empty.")

        items = list(
            cart.items.select_related("variant__product").order_by("created_at")
        )
        if not items:
            raise EmptyCartError("Your bag is empty.")

        # Lock every stock record involved, in UUID order, before validating.
        records = StockService.lock_stock_records([item.variant_id for item in items])

        for item in items:
            variant = item.variant
            product = variant.product
            if not variant.is_active or not product.is_published or product.is_deleted:
                raise UnavailableItemError(
                    f"'{product.title}' is no longer available for purchase."
                )

            record = records.get(variant.id)
            if record is None or record.available_quantity < item.quantity:
                available = record.available_quantity if record else 0
                if available == 0:
                    raise UnavailableItemError(
                        f"'{product.title}' ({variant.sku}) is out of stock."
                    )
                raise UnavailableItemError(
                    f"Only {available} unit(s) of '{variant.sku}' are available. "
                    "Please update your bag before ordering."
                )

        subtotal = Decimal("0.00")
        for item in items:
            line_total = item.line_total
            if line_total is None:
                raise UnavailableItemError(
                    f"'{item.variant.product.title}' has no price and cannot be ordered."
                )
            subtotal += line_total

        order = Order.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            session_key=session_key,
            customer_name=customer_name.strip(),
            customer_email=customer_email.strip(),
            customer_phone=customer_phone.strip(),
            shipping_address=shipping_address,
            notes=notes.strip(),
            payment_method=PaymentMethod.COD,
            subtotal=subtotal,
            shipping_fee=Decimal("0.00"),
            total=subtotal,
        )

        for item in items:
            variant = item.variant
            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_title=variant.product.title,
                variant_sku=variant.sku,
                size=variant.size,
                color_name=variant.color_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                line_total=item.line_total,
            )

        # Deduct stock through the inventory service so each sale is ledgered.
        for item in items:
            record = records[item.variant_id]
            new_on_hand = record.quantity_on_hand - item.quantity
            StockService.set_stock_level(
                variant_or_id=item.variant_id,
                new_quantity_on_hand=new_on_hand,
                reason=MovementReason.ORDER_CHECKOUT,
                actor=user if getattr(user, "is_authenticated", False) else None,
                notes=f"Sold via order {order.order_number}.",
                reference_id=str(order.id),
            )
            # Keep the catalog mirror used by the staff dashboard in sync so a
            # later product edit does not resync sold units back into inventory.
            item.variant.stock = new_on_hand
            item.variant.save(update_fields=["stock", "updated_at"])

        CartService.clear_cart(cart)
        return order

    @classmethod
    @transaction.atomic
    def update_status(
        cls, order_id, new_status: str, *, actor=None, note: str = ""
    ) -> Order:
        """Move an order through its fulfilment lifecycle (staff action).

        Cancelling or returning an order puts the *outstanding* units back into
        stock through ``StockService`` so the inventory ledger stays the single
        source of truth. Units already returned line-by-line are not restocked
        twice. Terminal states (``CANCELLED``/``RETURNED``) cannot be reopened,
        which also guarantees stock is never restored twice.

        Every transition is written to ``OrderStatusChange`` with the acting
        staff account so the dashboard can show an audit trail.

        Raises:
            OrderValidationError: Unknown status, or a change away from a
                terminal status.
        """
        if new_status not in OrderStatus.values:
            raise OrderValidationError("Unknown order status.")

        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status == new_status:
            return order
        if order.status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
            raise OrderValidationError(
                f"Order {order.order_number} is "
                f"{order.get_status_display().lower()} and cannot change status."
            )

        previous_status = order.status
        items = list(order.items.select_related("variant"))
        restockable = [item for item in items if item.variant_id]
        records = StockService.lock_stock_records(
            [item.variant_id for item in restockable]
        )

        if new_status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
            reason = (
                MovementReason.ORDER_CANCELLED
                if new_status == OrderStatus.CANCELLED
                else MovementReason.RETURN
            )
            for item in restockable:
                outstanding = item.remaining_quantity
                if outstanding <= 0:
                    continue
                record = records.get(item.variant_id)
                if record is None:
                    continue
                StockService.increase_stock(
                    item.variant_id,
                    outstanding,
                    reason=reason,
                    actor=actor,
                    notes=f"Returned to stock from order {order.order_number}.",
                    reference_id=str(order.id),
                )
                record.refresh_from_db()
                item.variant.stock = record.quantity_on_hand
                item.variant.save(update_fields=["stock", "updated_at"])
                # Mark the units accounted for so nothing can be returned twice.
                item.returned_quantity = item.quantity
                item.save(update_fields=["returned_quantity"])

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        OrderStatusChange.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=actor if getattr(actor, "is_authenticated", False) else None,
            note=note,
        )
        return order

    @classmethod
    @transaction.atomic
    def return_items(
        cls,
        order_id,
        quantities: dict[int, int],
        *,
        actor=None,
        note: str = "",
    ) -> Order:
        """Return selected units of individual order lines back into stock.

        Args:
            order_id: Primary key of the order.
            quantities: Mapping of ``OrderItem`` primary key -> units to return.
                Zero/blank entries are ignored.
            actor: Staff user recording the return.
            note: Optional reason shown in the audit trail.

        Returns:
            The updated order (status becomes ``RETURNED`` once every line is
            fully returned).

        Raises:
            OrderValidationError: Nothing to return, an unknown line, an
                invalid/over-sized quantity, or an order that is not in a
                returnable state.
        """
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
            raise OrderValidationError(
                f"Order {order.order_number} is "
                f"{order.get_status_display().lower()}; its stock has already "
                "been restored."
            )
        if order.status not in RETURNABLE_STATUSES:
            raise OrderValidationError(
                "Confirm the order before recording a return."
            )

        items = {item.pk: item for item in order.items.select_related("variant")}
        requested = {pk: qty for pk, qty in quantities.items() if qty}
        if not requested:
            raise OrderValidationError("Enter at least one quantity to return.")

        for pk, qty in requested.items():
            item = items.get(pk)
            if item is None:
                raise OrderValidationError("That line does not belong to this order.")
            if not isinstance(qty, int) or qty <= 0:
                raise OrderValidationError(
                    "Return quantities must be positive whole numbers."
                )
            if qty > item.remaining_quantity:
                raise OrderValidationError(
                    f"Cannot return {qty} x {item.variant_sku}: only "
                    f"{item.remaining_quantity} left to return."
                )

        restockable = [items[pk] for pk in requested if items[pk].variant_id]
        records = StockService.lock_stock_records(
            [item.variant_id for item in restockable]
        )
        total_returned = 0
        for item in restockable:
            qty = requested[item.pk]
            record = records.get(item.variant_id)
            if record is not None:
                StockService.increase_stock(
                    item.variant_id,
                    qty,
                    reason=MovementReason.RETURN,
                    actor=actor,
                    notes=f"Return recorded for order {order.order_number}.",
                    reference_id=str(order.id),
                )
                record.refresh_from_db()
                item.variant.stock = record.quantity_on_hand
                item.variant.save(update_fields=["stock", "updated_at"])
            total_returned += qty
            item.returned_quantity += qty
            item.save(update_fields=["returned_quantity"])

        previous_status = order.status
        fully_returned = all(item.is_fully_returned for item in items.values())
        if fully_returned and order.status != OrderStatus.RETURNED:
            order.status = OrderStatus.RETURNED
            order.save(update_fields=["status", "updated_at"])

        OrderStatusChange.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=order.status,
            changed_by=actor if getattr(actor, "is_authenticated", False) else None,
            note=note or f"Returned {total_returned} unit(s) to stock.",
        )
        return order

    @classmethod
    @transaction.atomic
    def request_return(
        cls,
        order_id,
        quantities: dict[int, int],
        *,
        requested_by=None,
        reason: str = "",
    ) -> ReturnRequest:
        """Record a customer's request to return units of a delivered order.

        Nothing is restocked here: the request only records intent and waits
        for staff review, because the units must physically come back first.

        Args:
            order_id: Primary key of the order being returned from.
            quantities: Mapping of ``OrderItem`` primary key -> units to return.
            requested_by: The authenticated customer, if any (guests pass None).
            reason: Customer-supplied explanation shown to staff.

        Raises:
            OrderValidationError: The order is not delivered, an open request
                already exists, nothing was selected, or a quantity exceeds
                what remains on that line.
        """
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status not in CUSTOMER_RETURNABLE_STATUSES:
            raise OrderValidationError(
                "You can request a return once your order has been delivered."
            )
        if order.return_requests.filter(status=ReturnRequestStatus.REQUESTED).exists():
            raise OrderValidationError(
                "You already have a return request awaiting review."
            )

        items = {item.pk: item for item in order.items.select_related("variant")}
        requested = {pk: qty for pk, qty in quantities.items() if qty}
        if not requested:
            raise OrderValidationError("Select at least one item to return.")

        for pk, qty in requested.items():
            item = items.get(pk)
            if item is None:
                raise OrderValidationError(
                    "That line does not belong to this order."
                )
            if not isinstance(qty, int) or qty <= 0:
                raise OrderValidationError(
                    "Return quantities must be positive whole numbers."
                )
            if qty > item.remaining_quantity:
                raise OrderValidationError(
                    f"Cannot return {qty} x {item.variant_sku}: only "
                    f"{item.remaining_quantity} left to return."
                )

        return_request = ReturnRequest.objects.create(
            order=order,
            requested_by=(
                requested_by
                if getattr(requested_by, "is_authenticated", False)
                else None
            ),
            reason=reason.strip(),
        )
        ReturnRequestItem.objects.bulk_create(
            [
                ReturnRequestItem(
                    request=return_request,
                    order_item=items[pk],
                    quantity=qty,
                )
                for pk, qty in requested.items()
            ]
        )
        return return_request

    @classmethod
    @transaction.atomic
    def review_return_request(
        cls,
        request_id,
        *,
        approve: bool,
        actor=None,
        note: str = "",
    ) -> ReturnRequest:
        """Approve (restock) or decline a customer return request.

        Approval delegates to :meth:`return_items`, so the stock movements,
        ``OrderItem.returned_quantity`` updates and the audit entry are exactly
        the same as a staff-recorded return. Each request can be reviewed once.

        Raises:
            OrderValidationError: The request was already reviewed, or approving
                it would return more units than remain on a line.
        """
        return_request = (
            ReturnRequest.objects.select_for_update()
            .select_related("order")
            .get(pk=request_id)
        )
        if not return_request.is_open:
            raise OrderValidationError(
                "This return request has already been reviewed."
            )

        note = note.strip()
        if approve:
            quantities = {
                item.order_item_id: item.quantity
                for item in return_request.items.all()
            }
            cls.return_items(
                return_request.order_id,
                quantities,
                actor=actor,
                note=note
                or f"Return request approved. {return_request.reason}".strip(),
            )
            return_request.status = ReturnRequestStatus.APPROVED
        else:
            return_request.status = ReturnRequestStatus.DECLINED

        return_request.staff_note = note
        return_request.resolved_at = timezone.now()
        return_request.resolved_by = (
            actor if getattr(actor, "is_authenticated", False) else None
        )
        return_request.save(
            update_fields=["status", "staff_note", "resolved_at", "resolved_by"]
        )
        return return_request

    @staticmethod
    def _validate_owner(cart: Cart | None, *, user, session_key: str) -> None:
        """Ensure the resolved owner matches the cart's owner (defence in depth)."""
        if cart is None:
            return
        if user is not None and getattr(user, "is_authenticated", False):
            if cart.user_id != user.pk:
                raise OrderValidationError("This bag does not belong to you.")
            return
        if not session_key or cart.session_key != session_key:
            raise OrderValidationError("Your bag session has expired.")
