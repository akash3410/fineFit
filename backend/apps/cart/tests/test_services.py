"""
PostgreSQL-backed tests for CartService: lifecycle, line-item operations,
validation, merge behaviour, and transactional atomicity.
"""

import pytest
from decimal import Decimal

from apps.cart.exceptions import (
    CartItemNotFoundError,
    CartValidationError,
)
from apps.cart.models import Cart, CartItem
from apps.cart.services import CartService
from apps.inventory.models import StockRecord


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Cart lifecycle
# ---------------------------------------------------------------------------


class TestGetOrCreateCart:
    def test_creates_cart_for_authenticated_user(self, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        assert cart.user_id == regular_user.id
        assert cart.session_key is None
        # Idempotent: the same active cart is returned again.
        again = CartService.get_or_create_cart(user=regular_user)
        assert again.id == cart.id
        assert Cart.objects.count() == 1

    def test_creates_cart_for_guest_session(self):
        session_key = "sess-createtest-0001"
        cart = CartService.get_or_create_cart(session_key=session_key)
        assert cart.session_key == session_key
        assert cart.user is None
        assert Cart.objects.count() == 1

    def test_rejects_both_owner_kinds(self, regular_user):
        with pytest.raises(CartValidationError):
            CartService.get_or_create_cart(user=regular_user, session_key="sess-1")

    def test_rejects_neither_owner_kind(self):
        with pytest.raises(CartValidationError):
            CartService.get_or_create_cart()

    def test_get_cart_returns_none_when_absent(self, regular_user):
        assert CartService.get_cart(user=regular_user) is None
        assert CartService.get_cart(session_key="sess-none") is None


# ---------------------------------------------------------------------------
# Add item
# ---------------------------------------------------------------------------


class TestAddItem:
    def test_add_creates_line_and_totals(
        self, variant, stock_record, regular_user
    ):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=2)

        item = cart.items.get(variant_id=variant.id)
        assert item.quantity == 2
        assert cart.total_quantity == 2
        assert cart.subtotal == Decimal("240.00")

    def test_adding_same_variant_merges_into_existing_line(
        self, variant, stock_record, regular_user
    ):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        CartService.add_item(cart, variant, quantity=2)

        assert cart.items.count() == 1
        item = cart.items.get()
        assert item.quantity == 3  # 1 + 2 combined, one line only
        assert cart.subtotal == Decimal("360.00")

    def test_accepts_variant_instance_and_uuid_string(
        self, variant, stock_record, regular_user
    ):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant.id, quantity=1)
        CartService.add_item(cart, str(variant.id), quantity=1)
        assert cart.items.get().quantity == 2

    def test_rejects_invalid_uuid(self, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, "not-a-uuid")
        assert cart.items.count() == 0

    def test_rejects_unknown_variant(self, regular_user):
        import uuid

        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, uuid.uuid4())
        assert cart.items.count() == 0

    def test_rejects_draft_product(self, draft_variant, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, draft_variant, quantity=1)
        assert cart.items.count() == 0

    def test_rejects_inactive_variant(self, inactive_variant, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, inactive_variant, quantity=1)
        assert cart.items.count() == 0

    def test_rejects_variant_without_stock_record(
        self, variant, regular_user
    ):
        """Missing StockRecord is treated as unavailable."""
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=1)
        assert cart.items.count() == 0

    def test_rejects_zero_stock(self, empty_stock_variant, zero_stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, empty_stock_variant, quantity=1)
        assert cart.items.count() == 0

    def test_rejects_quantity_exceeding_available(
        self, variant, stock_record, regular_user
    ):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError) as err:
            CartService.add_item(cart, variant, quantity=11)
        assert "Only 10 unit(s)" in str(err.value)
        assert cart.items.count() == 0

    def test_rejects_combined_quantity_exceeding_available(
        self, variant, stock_record, regular_user
    ):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=6)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=6)

    def test_rejects_non_integer_quantity(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity="2")
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=1.5)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=True)

    def test_rejects_zero_and_max_quantity(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=0)
        with pytest.raises(CartValidationError):
            CartService.add_item(cart, variant, quantity=1000)


# ---------------------------------------------------------------------------
# Update / remove / clear
# ---------------------------------------------------------------------------


class TestUpdateItemQuantity:
    def test_update_quantity(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        identifier = cart.items.get().pk
        CartService.update_item_quantity(cart, identifier, 4)
        assert cart.items.get().quantity == 4
        assert cart.subtotal == Decimal("480.00")

    def test_update_by_variant_identifier(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        CartService.update_item_quantity(cart, str(variant.id), 3)
        assert cart.items.get().quantity == 3

    def test_update_rechecks_availability(
        self, variant, stock_record, regular_user
    ):
        """Availability is re-validated on every quantity update."""
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        stock_record.quantity_reserved = 8  # only 2 now available
        stock_record.save(update_fields=["quantity_reserved"])
        with pytest.raises(CartValidationError) as err:
            CartService.update_item_quantity(cart, cart.items.get().pk, 5)
        assert "Only 2 unit(s)" in str(err.value)

    def test_update_unknown_item_raises(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartItemNotFoundError):
            CartService.update_item_quantity(cart, 99999, 1)

    def test_update_invalid_quantity_type(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        with pytest.raises(CartValidationError):
            CartService.update_item_quantity(cart, cart.items.get().pk, "three")


class TestRemoveAndClear:
    def test_remove_item(self, variant, stock_record, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=2)
        identifier = cart.items.get().pk
        updated = CartService.remove_item(cart, identifier)
        assert updated.items.count() == 0

    def test_remove_cross_cart_item_is_not_possible(
        self, variant, variant_two, stock_record, regular_user, other_user
    ):
        """Items of another cart cannot be removed through a foreign cart."""
        foreign_cart = CartService.get_or_create_cart(user=other_user)
        CartService.add_item(foreign_cart, variant, quantity=1)
        my_cart = CartService.get_or_create_cart(user=regular_user)
        with pytest.raises(CartItemNotFoundError):
            CartService.remove_item(my_cart, foreign_cart.items.get().pk)
        assert foreign_cart.items.count() == 1

    def test_clear_cart(self, variant, variant_two, stock_record, stock_record_two, regular_user):
        cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(cart, variant, quantity=1)
        CartService.add_item(cart, variant_two, quantity=2)
        cleared = CartService.clear_cart(cart)
        assert cleared.items.count() == 0
        assert cart.items.count() == 0


# ---------------------------------------------------------------------------
# Guest -> user merge
# ---------------------------------------------------------------------------


class TestGuestMerge:
    def test_merge_transfers_guest_items_into_user_cart(
        self, variant, variant_two, stock_record, stock_record_two, regular_user
    ):
        session_key = "sess-mergebasic-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=2)
        CartService.add_item(guest_cart, variant_two, quantity=1)

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        assert conflicts == []
        assert user_cart.user_id == regular_user.id
        assert user_cart.total_quantity == 3
        assert user_cart.subtotal == Decimal("360.00")
        # The guest cart no longer exists.
        assert not Cart.objects.filter(session_key=session_key).exists()

    def test_merge_duplicate_variant_combines_quantities(
        self, variant, stock_record, regular_user
    ):
        session_key = "sess-mergedup-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=2)
        user_cart_before = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(user_cart_before, variant, quantity=1)

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        item = user_cart.items.get(variant_id=variant.id)
        assert item.quantity == 3  # combined, nothing discarded
        assert user_cart.items.count() == 1

    def test_merge_reports_stock_conflict_without_discarding(
        self, variant, stock_record, regular_user
    ):
        """Merged quantity may exceed stock; the conflict is surfaced, not dropped."""
        session_key = "sess-mergeconflict-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=5)
        user_cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(user_cart, variant, quantity=4)  # 9 combined > 6 avail
        stock_record.quantity_on_hand = 6
        stock_record.save(update_fields=["quantity_on_hand"])

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        item = user_cart.items.get(variant_id=variant.id)
        assert item.quantity == 9  # never silently discarded
        assert conflicts == [
            {
                "variant_id": str(variant.id),
                "sku": variant.sku,
                "quantity": 9,
                "available_quantity": 6,
                "reason": "INSUFFICIENT_STOCK",
            }
        ]

    def test_merge_missing_stock_record_flagged_as_out_of_stock(
        self, variant, regular_user
    ):
        """A line whose StockRecord disappeared is flagged as OUT_OF_STOCK."""
        session_key = "sess-mergenorecord-0001"
        # There is no StockRecord for this variant, so the line cannot be
        # added via the service; create the stale guest line directly to
        # simulate inventory changing after the item was staged.
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartItem.objects.create(cart=guest_cart, variant=variant, quantity=2)

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        assert conflicts[0]["reason"] == "OUT_OF_STOCK"
        assert user_cart.items.filter(variant_id=variant.id).exists()

    def test_merge_reports_unpublished_variant_conflict(
        self, product, regular_user, draft_variant
    ):
        """Unpublished/inactive variants are preserved and flagged."""
        session_key = "sess-mergedraft-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartItem.objects.create(cart=guest_cart, variant=draft_variant, quantity=1)

        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            session_key, regular_user
        )
        assert conflicts[0]["reason"] == "VARIANT_UNAVAILABLE"
        assert user_cart.items.filter(variant_id=draft_variant.id).exists()

    def test_merge_with_no_guest_cart_is_noop(
        self, variant, stock_record, regular_user
    ):
        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            "sess-nonexistent-0001", regular_user
        )
        assert conflicts == []
        assert user_cart.user_id == regular_user.id

    def test_merge_with_missing_session_key_is_noop(
        self, regular_user
    ):
        user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
            None, regular_user
        )
        assert conflicts == []
        assert user_cart.user_id == regular_user.id
