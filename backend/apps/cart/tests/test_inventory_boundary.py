"""
PostgreSQL-backed tests proving the ADR-010 Option B inventory boundary:

Cart operations are ADVISORY-ONLY with respect to inventory. Adding,
updating, removing, clearing, and merging cart items must NEVER reserve,
release, decrement, or otherwise mutate StockRecord balances, and must NEVER
create StockMovement audit rows.
"""

import pytest
from rest_framework.test import APIClient

from apps.inventory.models import StockMovement, StockRecord
from apps.cart.models import Cart
from apps.cart.services import CartService

pytestmark = pytest.mark.django_db

CART_URL = "/api/v1/cart/"
ITEMS_URL = "/api/v1/cart/items/"


def _snapshot(variant):
    record = StockRecord.objects.get(variant_id=variant.id)
    return (record.quantity_on_hand, record.quantity_reserved)


def _movement_count(variant):
    return StockMovement.objects.filter(variant_id=variant.id).count()


class TestStockNotReservedByCartService:
    def test_adding_to_cart_does_not_reserve_stock(
        self, variant, stock_record
    ):
        before = _snapshot(variant)
        movements_before = _movement_count(variant)

        cart = CartService.get_or_create_cart(user=None, session_key="guest-bound-1")
        CartService.add_item(cart, variant, quantity=5)

        assert _snapshot(variant) == before, (
            "Adding to a cart must never change StockRecord balances"
        )
        assert _movement_count(variant) == movements_before

    def test_updating_cart_quantity_does_not_reserve_stock(
        self, variant, stock_record
    ):
        cart = CartService.get_or_create_cart(session_key="guest-bound-2")
        CartService.add_item(cart, variant, quantity=1)
        before = _snapshot(variant)
        movements_before = _movement_count(variant)

        CartService.update_item_quantity(
            cart, cart.items.get().pk, 7  # within the available range (10)
        )

        assert _snapshot(variant) == before
        assert _movement_count(variant) == movements_before

    def test_removing_item_does_not_change_stock_record(
        self, variant, stock_record
    ):
        cart = CartService.get_or_create_cart(session_key="guest-bound-3")
        CartService.add_item(cart, variant, quantity=3)
        before = _snapshot(variant)
        movements = _movement_count(variant)

        CartService.remove_item(cart, cart.items.get().pk)

        assert _snapshot(variant) == before
        assert _movement_count(variant) == movements

    def test_clearing_cart_does_not_change_stock(
        self, variant, variant_two, stock_record, stock_record_two
    ):
        cart = CartService.get_or_create_cart(session_key="guest-bound-4")
        CartService.add_item(cart, variant, quantity=3)
        CartService.add_item(cart, variant_two, quantity=2)
        snapshot = (_snapshot(variant), _snapshot(variant_two))
        movements = (_movement_count(variant), _movement_count(variant_two))

        CartService.clear_cart(cart)

        assert (_snapshot(variant), _snapshot(variant_two)) == snapshot
        assert (_movement_count(variant), _movement_count(variant_two)) == movements

    def test_merging_documents_conflicts_without_reserving(
        self, variant, stock_record, regular_user
    ):
        session_key = "guest-bound-5"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=5)
        before = _snapshot(variant)
        movements_before = _movement_count(variant)

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        assert conflicts == []
        assert _snapshot(variant) == before
        assert _movement_count(variant) == movements_before  # no audit rows added


class TestStockNotReservedByCartAPI:
    def test_api_add_update_remove_leave_stock_untouched(
        self, user_client, variant, variant_two, stock_record, stock_record_two
    ):
        before = (_snapshot(variant), _snapshot(variant_two))
        movements = (_movement_count(variant), _movement_count(variant_two))

        added = user_client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 4},
            content_type="application/json",
        )
        assert added.status_code == 201
        item_id = added.json()["items"][0]["id"]

        user_client.patch(
            f"{ITEMS_URL}{item_id}/",
            data={"quantity": 6},
            content_type="application/json",
        )
        user_client.delete(f"{ITEMS_URL}{item_id}/")
        user_client.delete(CART_URL)

        assert (_snapshot(variant), _snapshot(variant_two)) == before
        assert (_movement_count(variant), _movement_count(variant_two)) == movements

    def test_no_stockmovements_created_by_cart_only_operations(
        self, variant, stock_record
    ):
        initial = StockMovement.objects.count()
        cart = CartService.get_or_create_cart(session_key="guest-bound-6")
        CartService.add_item(cart, variant, quantity=2)
        CartService.update_item_quantity(cart, cart.items.get().pk, 4)
        CartService.remove_item(cart, cart.items.get().pk)
        CartService.clear_cart(cart)

        assert StockMovement.objects.count() == initial

    def test_stockavailability_checks_are_read_only_during_concurrent_reduction(
        self, variant, stock_record, regular_user
    ):
        """
        Between add-time and a later update, other shoppers may sell stock.
        The cart RE-CHECKS availability at update-time but never writes stock.
        """
        cart = CartService.get_or_create_cart(session_key="guest-bound-7")
        CartService.add_item(cart, variant, quantity=2)
        movements_before = _movement_count(variant)

        # Someone else consumes 9 units directly through the inventory service.
        from apps.inventory.services import StockService
        from apps.inventory.exceptions import InsufficientStockError
        from apps.cart.exceptions import CartValidationError

        with pytest.raises(InsufficientStockError):
            # (deliberately fail a decrease larger than available)
            StockService.decrease_stock(variant.id, 15, reason="ORDER_CHECKOUT")

        # Reduce by what is actually available, from an unrelated checkout.
        StockService.decrease_stock(variant.id, 9, reason="ORDER_CHECKOUT")
        assert _snapshot(variant) == (1, 0)  # 10 - 9, no reservations

        # Cart update is now rejected (advisory check), stock untouched.
        with pytest.raises(CartValidationError):
            CartService.update_item_quantity(cart, cart.items.get().pk, 2)
        assert _snapshot(variant) == (1, 0)
        assert _movement_count(variant) == movements_before + 1

        # The stale cart line is still staged (Phase 4B re-validates at checkout).
        assert cart.items.get().quantity == 2
