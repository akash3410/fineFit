"""
StockService: Transactional business operations for inventory management.

All stock alterations and reservation changes MUST go through this service.
All mutations execute within PostgreSQL transactions with row-level pessimistic
locking (``select_for_update``) to guarantee serialization and prevent overselling.

Deadlock Prevention:
--------------------
When acquiring row-level locks on multiple variants simultaneously (e.g., in a
cart or order checkout), variant IDs are strictly sorted before issuing
``select_for_update()`` to ensure a globally consistent lock acquisition order.
"""

import uuid
from typing import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import ProductVariant
from .exceptions import (
    InsufficientStockError,
    InvalidReservationError,
    InvalidStockAdjustmentError,
    StockRecordNotFoundError,
)
from .models import MovementReason, StockMovement, StockRecord


class StockService:
    """Service layer providing atomic operations for variant inventory."""

    @staticmethod
    def _resolve_variant_id(variant_or_id: ProductVariant | uuid.UUID | str) -> uuid.UUID:
        """Resolve a variant instance or UUID identifier into a clean UUID."""
        if isinstance(variant_or_id, ProductVariant):
            return variant_or_id.id
        if isinstance(variant_or_id, uuid.UUID):
            return variant_or_id
        try:
            return uuid.UUID(str(variant_or_id))
        except (ValueError, TypeError) as err:
            raise InvalidStockAdjustmentError(f"Invalid variant UUID: {variant_or_id}") from err

    @classmethod
    @transaction.atomic
    def get_stock_record_locked(
        cls, variant_or_id: ProductVariant | uuid.UUID | str
    ) -> StockRecord:
        """
        Fetch the StockRecord for a variant with a row-level pessimistic lock.

        Raises:
            StockRecordNotFoundError: If no StockRecord exists for the variant.
        """
        variant_id = cls._resolve_variant_id(variant_or_id)
        try:
            return (
                StockRecord.objects.select_for_update()
                .select_related("variant")
                .get(variant_id=variant_id)
            )
        except StockRecord.DoesNotExist as err:
            raise StockRecordNotFoundError(
                f"No StockRecord exists for variant ID '{variant_id}'."
            ) from err

    @classmethod
    @transaction.atomic
    def create_stock_record(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity_on_hand: int = 0,
        quantity_reserved: int = 0,
        low_stock_threshold: int = 5,
        actor=None,
        reason: str = MovementReason.INITIAL_STOCK,
        notes: str = "",
        reference_id: str = "",
    ) -> StockRecord:
        """
        Create an initial StockRecord for a variant and record an initial audit movement.

        Raises:
            InvalidStockAdjustmentError: If quantities violate constraints or record exists.
        """
        variant_id = cls._resolve_variant_id(variant_or_id)
        if quantity_on_hand < 0:
            raise InvalidStockAdjustmentError("Quantity on hand cannot be negative.")
        if quantity_reserved < 0:
            raise InvalidStockAdjustmentError("Quantity reserved cannot be negative.")
        if quantity_reserved > quantity_on_hand:
            raise InvalidStockAdjustmentError(
                "Quantity reserved cannot exceed initial quantity on hand."
            )
        if low_stock_threshold < 0:
            raise InvalidStockAdjustmentError("Low stock threshold cannot be negative.")

        if StockRecord.objects.filter(variant_id=variant_id).exists():
            raise InvalidStockAdjustmentError(
                f"StockRecord already exists for variant '{variant_id}'."
            )

        try:
            variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist as err:
            raise InvalidStockAdjustmentError(
                f"ProductVariant with ID '{variant_id}' does not exist."
            ) from err

        record = StockRecord(
            variant=variant,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            low_stock_threshold=low_stock_threshold,
        )
        record.full_clean()
        record.save()

        if quantity_on_hand > 0 or quantity_reserved > 0:
            StockMovement.objects.create(
                stock_record=record,
                variant=variant,
                quantity_delta=quantity_on_hand,
                reserved_delta=quantity_reserved,
                reason=reason,
                notes=notes or "Initial stock balance established.",
                reference_id=reference_id,
                actor=actor,
            )

        return record

    @classmethod
    @transaction.atomic
    def increase_stock(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity: int,
        reason: str = MovementReason.PURCHASE_RECEIPT,
        actor=None,
        notes: str = "",
        reference_id: str = "",
    ) -> StockRecord:
        """
        Increase physical on-hand stock for a variant.

        Args:
            variant_or_id: The variant instance or UUID.
            quantity: Positive integer quantity to add.
            reason: MovementReason choice.
            actor: Optional user performing the action.
            notes: Contextual notes.
            reference_id: External identifier (e.g. PO number).

        Returns:
            Updated StockRecord.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidStockAdjustmentError("Quantity to increase must be a positive integer.")

        record = cls.get_stock_record_locked(variant_or_id)
        record.quantity_on_hand += quantity
        record.full_clean()
        record.save(update_fields=["quantity_on_hand", "updated_at"])

        StockMovement.objects.create(
            stock_record=record,
            variant=record.variant,
            quantity_delta=quantity,
            reserved_delta=0,
            reason=reason,
            notes=notes,
            reference_id=reference_id,
            actor=actor,
        )
        return record

    @classmethod
    @transaction.atomic
    def decrease_stock(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity: int,
        reason: str = MovementReason.ORDER_CHECKOUT,
        actor=None,
        notes: str = "",
        reference_id: str = "",
        from_reserved: bool = False,
    ) -> StockRecord:
        """
        Decrease physical on-hand stock with availability checks.

        Args:
            variant_or_id: The variant instance or UUID.
            quantity: Positive integer quantity to subtract.
            reason: MovementReason choice.
            actor: Optional user performing the action.
            notes: Contextual notes.
            reference_id: External identifier (e.g. Order ID).
            from_reserved: If True, the quantity was previously reserved (e.g., checkout
                completing an existing reservation), so both on_hand and reserved are decremented.
                If False, requires sufficient unreserved (available) stock.

        Raises:
            InsufficientStockError: If available or reserved stock is insufficient.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidStockAdjustmentError("Quantity to decrease must be a positive integer.")

        record = cls.get_stock_record_locked(variant_or_id)

        if from_reserved:
            if record.quantity_reserved < quantity:
                raise InsufficientStockError(
                    f"Insufficient reserved stock for variant {record.variant.sku}: "
                    f"requested {quantity}, reserved {record.quantity_reserved}."
                )
            if record.quantity_on_hand < quantity:
                raise InsufficientStockError(
                    f"Insufficient physical stock for variant {record.variant.sku}: "
                    f"requested {quantity}, on-hand {record.quantity_on_hand}."
                )
            record.quantity_on_hand -= quantity
            record.quantity_reserved -= quantity
            reserved_delta = -quantity
        else:
            if record.available_quantity < quantity:
                raise InsufficientStockError(
                    f"Insufficient available stock for variant {record.variant.sku}: "
                    f"requested {quantity}, available {record.available_quantity}."
                )
            record.quantity_on_hand -= quantity
            reserved_delta = 0

        record.full_clean()
        record.save(update_fields=["quantity_on_hand", "quantity_reserved", "updated_at"])

        StockMovement.objects.create(
            stock_record=record,
            variant=record.variant,
            quantity_delta=-quantity,
            reserved_delta=reserved_delta,
            reason=reason,
            notes=notes,
            reference_id=reference_id,
            actor=actor,
        )
        return record

    @classmethod
    @transaction.atomic
    def reserve_stock(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity: int,
        reason: str = MovementReason.RESERVATION,
        actor=None,
        notes: str = "",
        reference_id: str = "",
    ) -> StockRecord:
        """
        Reserve stock for an order or session.

        Available stock is reduced while physical on-hand stock remains unchanged.

        Raises:
            InsufficientStockError: If available stock is less than requested quantity.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidStockAdjustmentError("Quantity to reserve must be a positive integer.")

        record = cls.get_stock_record_locked(variant_or_id)

        if record.available_quantity < quantity:
            raise InsufficientStockError(
                f"Insufficient available stock to reserve variant {record.variant.sku}: "
                f"requested {quantity}, available {record.available_quantity}."
            )

        record.quantity_reserved += quantity
        record.full_clean()
        record.save(update_fields=["quantity_reserved", "updated_at"])

        StockMovement.objects.create(
            stock_record=record,
            variant=record.variant,
            quantity_delta=0,
            reserved_delta=quantity,
            reason=reason,
            notes=notes,
            reference_id=reference_id,
            actor=actor,
        )
        return record

    @classmethod
    @transaction.atomic
    def release_reservation(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity: int,
        reason: str = MovementReason.RESERVATION_RELEASE,
        actor=None,
        notes: str = "",
        reference_id: str = "",
    ) -> StockRecord:
        """
        Release a previously held reservation back into available stock.

        Raises:
            InvalidReservationError: If requested quantity exceeds currently reserved units.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidStockAdjustmentError("Quantity to release must be a positive integer.")

        record = cls.get_stock_record_locked(variant_or_id)

        if record.quantity_reserved < quantity:
            raise InvalidReservationError(
                f"Cannot release {quantity} units for variant {record.variant.sku}; "
                f"only {record.quantity_reserved} units are reserved."
            )

        record.quantity_reserved -= quantity
        record.full_clean()
        record.save(update_fields=["quantity_reserved", "updated_at"])

        StockMovement.objects.create(
            stock_record=record,
            variant=record.variant,
            quantity_delta=0,
            reserved_delta=-quantity,
            reason=reason,
            notes=notes,
            reference_id=reference_id,
            actor=actor,
        )
        return record

    @classmethod
    @transaction.atomic
    def set_stock_level(
        cls,
        variant_or_id: ProductVariant | uuid.UUID | str,
        new_quantity_on_hand: int,
        reason: str = MovementReason.CORRECTION,
        actor=None,
        notes: str = "",
        reference_id: str = "",
    ) -> StockRecord:
        """
        Set on-hand physical inventory to an absolute count (e.g. inventory audit).

        Raises:
            InvalidStockAdjustmentError: If new count is negative or lower than reserved units.
        """
        if not isinstance(new_quantity_on_hand, int) or new_quantity_on_hand < 0:
            raise InvalidStockAdjustmentError(
                "New quantity on hand must be a non-negative integer."
            )

        record = cls.get_stock_record_locked(variant_or_id)

        if new_quantity_on_hand < record.quantity_reserved:
            raise InvalidStockAdjustmentError(
                f"Cannot set on-hand stock to {new_quantity_on_hand}; "
                f"must be at least the reserved quantity ({record.quantity_reserved})."
            )

        delta = new_quantity_on_hand - record.quantity_on_hand
        if delta == 0:
            # No change in quantity on hand
            return record

        record.quantity_on_hand = new_quantity_on_hand
        record.full_clean()
        record.save(update_fields=["quantity_on_hand", "updated_at"])

        StockMovement.objects.create(
            stock_record=record,
            variant=record.variant,
            quantity_delta=delta,
            reserved_delta=0,
            reason=reason,
            notes=notes or "Stock count adjusted via physical inventory audit.",
            reference_id=reference_id,
            actor=actor,
        )
        return record

    @classmethod
    @transaction.atomic
    def lock_stock_records(
        cls, variant_ids: Sequence[uuid.UUID | str]
    ) -> dict[uuid.UUID, StockRecord]:
        """
        Batch-lock StockRecords for multiple variants in deterministic order.

        Sorting the variant UUIDs prevents PostgreSQL deadlock conditions when
        concurrent operations touch overlapping sets of variants.

        Returns:
            Dictionary mapping variant UUID -> locked StockRecord.
        """
        clean_ids = sorted(list({cls._resolve_variant_id(v_id) for v_id in variant_ids}))
        if not clean_ids:
            return {}

        records = (
            StockRecord.objects.select_for_update()
            .select_related("variant")
            .filter(variant_id__in=clean_ids)
        )
        return {record.variant_id: record for record in records}

