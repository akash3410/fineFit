"""
Tests for inventory models: StockRecord and StockMovement.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.inventory.models import MovementReason, StockMovement, StockRecord


@pytest.mark.django_db
class TestStockRecordModel:
    def test_stock_record_creation_and_properties(self, variant):
        record = StockRecord.objects.create(
            variant=variant,
            quantity_on_hand=50,
            quantity_reserved=10,
            low_stock_threshold=5,
        )
        assert record.id is not None
        assert record.variant == variant
        assert record.quantity_on_hand == 50
        assert record.quantity_reserved == 10
        assert record.available_quantity == 40
        assert record.quantity_available == 40
        assert record.quantity == 50
        assert record.is_in_stock is True
        assert record.is_low_stock is False
        assert "SSD-BLK-M" in str(record)

    def test_one_to_one_relationship_enforced(self, variant, stock_record):
        with pytest.raises(IntegrityError):
            StockRecord.objects.create(
                variant=variant,
                quantity_on_hand=10,
            )

    def test_is_low_stock_property(self, variant):
        # available = 10 - 6 = 4 <= threshold 5 -> low stock
        record = StockRecord.objects.create(
            variant=variant,
            quantity_on_hand=10,
            quantity_reserved=6,
            low_stock_threshold=5,
        )
        assert record.available_quantity == 4
        assert record.is_in_stock is True
        assert record.is_low_stock is True

    def test_out_of_stock_property(self, variant):
        record = StockRecord.objects.create(
            variant=variant,
            quantity_on_hand=5,
            quantity_reserved=5,
            low_stock_threshold=5,
        )
        assert record.available_quantity == 0
        assert record.is_in_stock is False
        assert record.is_low_stock is False

    def test_model_clean_validation(self, variant):
        # Reserved cannot exceed on hand
        record = StockRecord(variant=variant, quantity_on_hand=5, quantity_reserved=6)
        with pytest.raises(ValidationError) as exc:
            record.clean()
        assert "quantity_reserved" in exc.value.error_dict

        # Negative on hand
        record_neg = StockRecord(variant=variant, quantity_on_hand=-1, quantity_reserved=0)
        with pytest.raises(ValidationError) as exc:
            record_neg.clean()
        assert "quantity_on_hand" in exc.value.error_dict

    def test_db_constraint_reserved_lte_on_hand(self, variant):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                StockRecord.objects.create(
                    variant=variant,
                    quantity_on_hand=5,
                    quantity_reserved=10,
                )

    def test_queryset_filters(self, product):
        from apps.catalog.models import ProductVariant

        v1 = ProductVariant.objects.create(product=product, sku="SKU-1", size="S")
        v2 = ProductVariant.objects.create(product=product, sku="SKU-2", size="M")
        v3 = ProductVariant.objects.create(product=product, sku="SKU-3", size="L")

        # In stock (healthy)
        StockRecord.objects.create(variant=v1, quantity_on_hand=20, quantity_reserved=0, low_stock_threshold=5)
        # Low stock (available=3 <= 5)
        StockRecord.objects.create(variant=v2, quantity_on_hand=5, quantity_reserved=2, low_stock_threshold=5)
        # Out of stock (available=0)
        StockRecord.objects.create(variant=v3, quantity_on_hand=4, quantity_reserved=4, low_stock_threshold=5)

        assert StockRecord.objects.in_stock().count() == 2
        assert StockRecord.objects.low_stock().count() == 1
        assert StockRecord.objects.low_stock().first().variant == v2
        assert StockRecord.objects.out_of_stock().count() == 1
        assert StockRecord.objects.out_of_stock().first().variant == v3


@pytest.mark.django_db
class TestStockMovementModel:
    def test_stock_movement_creation(self, stock_record, regular_user):
        movement = StockMovement.objects.create(
            stock_record=stock_record,
            variant=stock_record.variant,
            quantity_delta=10,
            reserved_delta=0,
            reason=MovementReason.PURCHASE_RECEIPT,
            notes="Received shipment PO-9988",
            reference_id="PO-9988",
            actor=regular_user,
        )
        assert movement.id is not None
        assert movement.stock_record == stock_record
        assert movement.variant == stock_record.variant
        assert movement.actor == regular_user
        assert movement.quantity_delta == 10
        assert movement.reason == MovementReason.PURCHASE_RECEIPT
        assert "PO-9988" in str(movement)

    def test_stock_movement_is_immutable_against_update(self, stock_record):
        movement = StockMovement.objects.create(
            stock_record=stock_record,
            variant=stock_record.variant,
            quantity_delta=5,
            reason=MovementReason.INITIAL_STOCK,
        )
        movement.notes = "Attempting modification"
        with pytest.raises(ValidationError, match="immutable audit logs and cannot be updated"):
            movement.save()

    def test_stock_movement_is_immutable_against_deletion(self, stock_record):
        movement = StockMovement.objects.create(
            stock_record=stock_record,
            variant=stock_record.variant,
            quantity_delta=5,
            reason=MovementReason.INITIAL_STOCK,
        )
        with pytest.raises(ValidationError, match="immutable audit logs and cannot be deleted"):
            movement.delete()

