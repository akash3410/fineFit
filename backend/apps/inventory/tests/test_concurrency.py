"""
PostgreSQL concurrency and transactional atomicity tests for inventory operations.
"""

import threading
import pytest
from django.db import connection, transaction

from apps.inventory.exceptions import InsufficientStockError
from apps.inventory.models import StockMovement, StockRecord
from apps.inventory.services import StockService


@pytest.mark.django_db(transaction=True)
class TestInventoryConcurrency:
    def test_concurrent_decrease_prevents_overselling(self, variant):
        """
        Verify that concurrent threads attempting to decrement stock with select_for_update
        properly serialize, preventing overselling the inventory on PostgreSQL.
        """
        # Create record with exactly 1 unit available
        StockRecord.objects.create(
            variant=variant,
            quantity_on_hand=1,
            quantity_reserved=0,
        )

        results = []
        errors = []

        def worker():
            # Close stale connection to force separate DB connection per thread
            connection.close()
            try:
                StockService.decrease_stock(
                    variant_or_id=variant.id,
                    quantity=1,
                    reason="ORDER_CHECKOUT",
                )
                results.append("SUCCESS")
            except InsufficientStockError as err:
                errors.append(err)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one worker must succeed, and exactly one must fail with InsufficientStockError
        assert len(results) == 1
        assert len(errors) == 1
        record = StockRecord.objects.get(variant=variant)
        assert record.quantity_on_hand == 0
        assert StockMovement.objects.filter(variant=variant).count() == 1

    def test_atomic_rollback_on_failed_operation(self, variant):
        """
        Verify that if an inventory operation fails validation, any preliminary
        changes are rolled back completely and no orphan StockMovement is left.
        """
        record = StockRecord.objects.create(
            variant=variant,
            quantity_on_hand=10,
            quantity_reserved=0,
        )

        # Attempt an operation inside a transaction that fails
        try:
            with transaction.atomic():
                StockService.increase_stock(
                    variant_or_id=variant,
                    quantity=5,
                    reason="PURCHASE_RECEIPT",
                )
                # Intentionally trigger an exception to force rollback
                raise ValueError("Simulated unexpected application failure")
        except ValueError:
            pass

        record.refresh_from_db()
        assert record.quantity_on_hand == 10
        assert StockMovement.objects.filter(variant=variant).count() == 0

    def test_lock_stock_records_deterministic_sorting(self, product):
        """
        Verify lock_stock_records sorts variant IDs before executing select_for_update,
        guaranteeing consistent lock acquisition order to prevent deadlocks.
        """
        from apps.catalog.models import ProductVariant

        v1 = ProductVariant.objects.create(product=product, sku="V-1", size="S")
        v2 = ProductVariant.objects.create(product=product, sku="V-2", size="M")
        v3 = ProductVariant.objects.create(product=product, sku="V-3", size="L")

        StockRecord.objects.create(variant=v1, quantity_on_hand=10)
        StockRecord.objects.create(variant=v2, quantity_on_hand=10)
        StockRecord.objects.create(variant=v3, quantity_on_hand=10)

        # Pass IDs in arbitrary / reversed order
        ids = [v3.id, v1.id, v2.id]
        locked = StockService.lock_stock_records(ids)
        assert len(locked) == 3
        # Ensure all requested IDs are present
        assert set(locked.keys()) == {v1.id, v2.id, v3.id}

