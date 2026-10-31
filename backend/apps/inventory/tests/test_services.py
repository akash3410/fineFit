"""
Tests for StockService operations and transactional guarantees.
"""

import pytest
from django.db import transaction

from apps.inventory.exceptions import (
    InsufficientStockError,
    InvalidReservationError,
    InvalidStockAdjustmentError,
    StockRecordNotFoundError,
)
from apps.inventory.models import MovementReason, StockMovement, StockRecord
from apps.inventory.services import StockService


@pytest.mark.django_db
class TestStockServiceCreation:
    def test_create_stock_record_success(self, variant, regular_user):
        record = StockService.create_stock_record(
            variant_or_id=variant,
            quantity_on_hand=30,
            quantity_reserved=5,
            low_stock_threshold=5,
            actor=regular_user,
            notes="Initial stock receipt",
            reference_id="INIT-1",
        )
        assert record.quantity_on_hand == 30
        assert record.quantity_reserved == 5
        assert record.available_quantity == 25

        movement = StockMovement.objects.get(stock_record=record)
        assert movement.quantity_delta == 30
        assert movement.reserved_delta == 5
        assert movement.reason == MovementReason.INITIAL_STOCK
        assert movement.actor == regular_user
        assert movement.reference_id == "INIT-1"

    def test_create_stock_record_zero_quantities_creates_no_movement(self, variant):
        record = StockService.create_stock_record(
            variant_or_id=variant,
            quantity_on_hand=0,
            quantity_reserved=0,
        )
        assert record.quantity_on_hand == 0
        assert StockMovement.objects.filter(stock_record=record).count() == 0

    def test_create_stock_record_duplicate_raises_error(self, variant, stock_record):
        with pytest.raises(InvalidStockAdjustmentError, match="already exists"):
            StockService.create_stock_record(variant_or_id=variant, quantity_on_hand=10)

    def test_create_stock_record_invalid_quantities_rejected(self, variant):
        with pytest.raises(InvalidStockAdjustmentError, match="cannot be negative"):
            StockService.create_stock_record(variant_or_id=variant, quantity_on_hand=-5)

        with pytest.raises(InvalidStockAdjustmentError, match="cannot exceed"):
            StockService.create_stock_record(
                variant_or_id=variant, quantity_on_hand=10, quantity_reserved=15
            )


@pytest.mark.django_db
class TestStockServiceMutations:
    def test_increase_stock(self, stock_record, regular_user):
        initial_on_hand = stock_record.quantity_on_hand
        updated = StockService.increase_stock(
            variant_or_id=stock_record.variant,
            quantity=15,
            reason=MovementReason.PURCHASE_RECEIPT,
            actor=regular_user,
            notes="Shipment PO-443",
            reference_id="PO-443",
        )
        assert updated.quantity_on_hand == initial_on_hand + 15

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == 15
        assert movement.reserved_delta == 0
        assert movement.reason == MovementReason.PURCHASE_RECEIPT
        assert movement.actor == regular_user

    def test_increase_stock_invalid_quantity_rejected(self, stock_record):
        with pytest.raises(InvalidStockAdjustmentError, match="positive integer"):
            StockService.increase_stock(variant_or_id=stock_record.variant, quantity=0)

        with pytest.raises(InvalidStockAdjustmentError, match="positive integer"):
            StockService.increase_stock(variant_or_id=stock_record.variant, quantity=-10)

    def test_decrease_stock_success(self, stock_record, regular_user):
        # Initial: on_hand=20, reserved=5, available=15
        updated = StockService.decrease_stock(
            variant_or_id=stock_record.variant,
            quantity=10,
            reason=MovementReason.ORDER_CHECKOUT,
            actor=regular_user,
            notes="Order checkout ORD-100",
            reference_id="ORD-100",
        )
        assert updated.quantity_on_hand == 10
        assert updated.quantity_reserved == 5
        assert updated.available_quantity == 5

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == -10
        assert movement.reserved_delta == 0
        assert movement.reason == MovementReason.ORDER_CHECKOUT

    def test_decrease_stock_insufficient_stock_rejected(self, stock_record):
        # Initial available: 15. Attempting to decrease 16
        with pytest.raises(InsufficientStockError, match="Insufficient available stock"):
            StockService.decrease_stock(
                variant_or_id=stock_record.variant,
                quantity=16,
            )
        # Ensure record was untouched
        stock_record.refresh_from_db()
        assert stock_record.quantity_on_hand == 20
        assert StockMovement.objects.count() == 0

    def test_decrease_stock_from_reserved(self, stock_record):
        # Initial: on_hand=20, reserved=5
        updated = StockService.decrease_stock(
            variant_or_id=stock_record.variant,
            quantity=3,
            from_reserved=True,
            reason=MovementReason.ORDER_CHECKOUT,
        )
        assert updated.quantity_on_hand == 17
        assert updated.quantity_reserved == 2
        assert updated.available_quantity == 15

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == -3
        assert movement.reserved_delta == -3

    def test_decrease_stock_from_reserved_exceeding_reserved_rejected(self, stock_record):
        # Initial reserved is 5. Attempting 6 from reserved
        with pytest.raises(InsufficientStockError, match="Insufficient reserved stock"):
            StockService.decrease_stock(
                variant_or_id=stock_record.variant,
                quantity=6,
                from_reserved=True,
            )


@pytest.mark.django_db
class TestStockServiceReservations:
    def test_reserve_stock_success(self, stock_record, regular_user):
        # Initial: on_hand=20, reserved=5, available=15
        updated = StockService.reserve_stock(
            variant_or_id=stock_record.variant,
            quantity=8,
            reason=MovementReason.RESERVATION,
            actor=regular_user,
            reference_id="CART-SESSION-1",
        )
        assert updated.quantity_on_hand == 20
        assert updated.quantity_reserved == 13
        assert updated.available_quantity == 7

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == 0
        assert movement.reserved_delta == 8
        assert movement.reason == MovementReason.RESERVATION

    def test_reserve_stock_insufficient_available_rejected(self, stock_record):
        # Available is 15. Attempting 16
        with pytest.raises(InsufficientStockError, match="Insufficient available stock to reserve"):
            StockService.reserve_stock(
                variant_or_id=stock_record.variant,
                quantity=16,
            )
        stock_record.refresh_from_db()
        assert stock_record.quantity_reserved == 5

    def test_release_reservation_success(self, stock_record, regular_user):
        # Initial reserved: 5
        updated = StockService.release_reservation(
            variant_or_id=stock_record.variant,
            quantity=3,
            reason=MovementReason.RESERVATION_RELEASE,
            actor=regular_user,
        )
        assert updated.quantity_reserved == 2
        assert updated.available_quantity == 18

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == 0
        assert movement.reserved_delta == -3

    def test_release_reservation_exceeding_reserved_rejected(self, stock_record):
        # Initial reserved is 5. Attempting 6
        with pytest.raises(InvalidReservationError, match="Cannot release 6 units"):
            StockService.release_reservation(
                variant_or_id=stock_record.variant,
                quantity=6,
            )
        stock_record.refresh_from_db()
        assert stock_record.quantity_reserved == 5


@pytest.mark.django_db
class TestStockServiceSetLevelAndBatchLock:
    def test_set_stock_level(self, stock_record):
        # Initial: on_hand=20, reserved=5
        updated = StockService.set_stock_level(
            variant_or_id=stock_record.variant,
            new_quantity_on_hand=35,
        )
        assert updated.quantity_on_hand == 35

        movement = StockMovement.objects.latest("created_at")
        assert movement.quantity_delta == 15

    def test_set_stock_level_below_reserved_rejected(self, stock_record):
        # Initial reserved is 5. Setting on_hand to 4 violates reserved <= on_hand
        with pytest.raises(InvalidStockAdjustmentError, match="must be at least the reserved"):
            StockService.set_stock_level(
                variant_or_id=stock_record.variant,
                new_quantity_on_hand=4,
            )

    def test_missing_stock_record_raises_error(self, variant_two):
        with pytest.raises(StockRecordNotFoundError):
            StockService.increase_stock(variant_or_id=variant_two, quantity=5)

    def test_lock_stock_records_batch(self, variant, variant_two, stock_record):
        record_two = StockRecord.objects.create(
            variant=variant_two, quantity_on_hand=15, quantity_reserved=0
        )
        locked = StockService.lock_stock_records([variant.id, variant_two.id])
        assert len(locked) == 2
        assert locked[variant.id].id == stock_record.id
        assert locked[variant_two.id].id == record_two.id

