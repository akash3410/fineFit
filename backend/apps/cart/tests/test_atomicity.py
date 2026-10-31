"""
PostgreSQL-backed tests for CartService transactional atomicity.
"""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.cart.exceptions import CartValidationError
from apps.cart.models import Cart, CartItem
from apps.cart.services import CartService
from apps.inventory.models import StockRecord


pytestmark = pytest.mark.django_db


class TestMergeAtomicity:
    def test_merge_rolls_back_and_preserves_guest_cart_on_error(
        self,
        variant,
        variant_two,
        stock_record,
        stock_record_two,
        regular_user,
        monkeypatch,
    ):
        """
        If any step of the merge fails, the whole transaction rolls back:
        the guest cart is untouched and no items leaked into the user cart.
        """
        session_key = "sess-atomicity-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=1)
        CartService.add_item(guest_cart, variant_two, quantity=1)

        original_full_clean = CartItem.full_clean
        calls = {"count": 0}

        def flaky_full_clean(self, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise DjangoValidationError("Simulated merge failure")
            return original_full_clean(self, *args, **kwargs)

        monkeypatch.setattr(CartItem, "full_clean", flaky_full_clean)

        with pytest.raises(CartValidationError):
            CartService.merge_guest_cart_into_user_cart(session_key, regular_user)

        # Guest cart (and both of its lines) survived the failed merge.
        assert Cart.objects.filter(session_key=session_key).exists()
        guest_cart.refresh_from_db()
        assert guest_cart.items.count() == 2
        # No items leaked into the customer's cart.
        assert not CartItem.objects.filter(cart__user=regular_user).exists()

        # Cart operations never touch inventory state.
        record = StockRecord.objects.get(variant_id=variant.id)
        assert (record.quantity_on_hand, record.quantity_reserved) == (10, 0)

    def test_merge_inside_explicit_transaction_preserves_all_or_nothing(
        self,
        variant,
        variant_two,
        stock_record,
        stock_record_two,
        regular_user,
        monkeypatch,
    ):
        """Merging within a caller-provided atomic block is all-or-nothing."""
        session_key = "sess-atomicity2-0001"
        guest_cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(guest_cart, variant, quantity=1)
        CartService.add_item(guest_cart, variant_two, quantity=1)

        def exploding_full_clean(self, *args, **kwargs):
            raise DjangoValidationError("boom")

        monkeypatch.setattr(CartItem, "full_clean", exploding_full_clean)

        with pytest.raises(CartValidationError):
            with transaction.atomic():
                CartService.merge_guest_cart_into_user_cart(session_key, regular_user)

        assert CartItem.objects.filter(cart__user=regular_user).count() == 0
        guest_cart.refresh_from_db()
        assert guest_cart.items.count() == 2
