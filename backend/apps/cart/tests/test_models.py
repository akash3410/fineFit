"""
PostgreSQL-backed tests for Cart and CartItem models: ownership integrity,
constraints, and trusted derived values.
"""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from decimal import Decimal

from apps.cart.models import Cart, CartItem


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Ownership & integrity constraints
# ---------------------------------------------------------------------------


class TestCartOwnership:
    def test_guest_cart_creation(self, stock_record, guest_session):
        """A cart can be created and persisted for a guest session key."""
        session_key = guest_session()
        cart = Cart.objects.create(session_key=session_key)
        fetched = Cart.objects.for_guest_session(session_key).get()
        assert fetched.id == cart.id
        assert cart.user is None

    def test_authenticated_cart_creation(self, stock_record, regular_user):
        """A cart can be created and persisted for an authenticated user."""
        cart = Cart.objects.create(user=regular_user)
        fetched = Cart.objects.for_user(regular_user).get()
        assert fetched.id == cart.id

    def test_cart_with_both_owners_rejected_by_db_constraint(self, stock_record, regular_user):
        """Ownership integrity: user AND session is rejected by the database."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(user=regular_user, session_key="abc-session-1")

    def test_cart_with_no_owner_rejected_by_db_constraint(self, stock_record):
        """Ownership integrity: neither user nor session is rejected."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create()

    def test_cart_with_empty_session_key_rejected_by_db_constraint(self, stock_record):
        """An empty session_key is not a valid guest owner."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(session_key="")

    def test_model_clean_rejects_both_and_neither_owners(self, stock_record, regular_user):
        """Model-level clean() backstop mirrors the database constraints."""
        both_owners = Cart(user=regular_user, session_key="abc-session-2")
        with pytest.raises(DjangoValidationError):
            both_owners.clean()

        no_owner = Cart()
        with pytest.raises(DjangoValidationError):
            no_owner.clean()

    def test_one_active_cart_per_user(self, stock_record, regular_user):
        """Partial unique index prevents two active carts for one customer."""
        Cart.objects.create(user=regular_user)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(user=regular_user)

    def test_one_active_cart_per_guest_session(self, stock_record, guest_session):
        """Partial unique index prevents two active carts per session key."""
        session_key = guest_session()
        Cart.objects.create(session_key=session_key)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Cart.objects.create(session_key=session_key)


# ---------------------------------------------------------------------------
# CartItem constraints
# ---------------------------------------------------------------------------


class TestCartItemConstraints:
    def test_cart_item_uniqueness_per_variant(
        self, variant, stock_record, regular_user
    ):
        """A cart cannot hold two lines for the same variant."""
        cart = Cart.objects.create(user=regular_user)
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(cart=cart, variant=variant, quantity=2)

    def test_same_variant_in_two_different_carts_is_allowed(
        self, variant, stock_record, regular_user, other_user
    ):
        """Uniqueness is per (cart, variant), not per variant globally."""
        cart_a = Cart.objects.create(user=regular_user)
        cart_b = Cart.objects.create(user=other_user)
        CartItem.objects.create(cart=cart_a, variant=variant, quantity=1)
        CartItem.objects.create(cart=cart_b, variant=variant, quantity=1)
        assert cart_a.items.count() == 1
        assert cart_b.items.count() == 1

    def test_quantity_positive_check_constraint(
        self, variant, stock_record, regular_user
    ):
        """The database rejects non-positive cart item quantities."""
        cart = Cart.objects.create(user=regular_user)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CartItem.objects.create(cart=cart, variant=variant, quantity=0)

    def test_model_clean_rejects_zero_quantity(
        self, variant, stock_record, regular_user
    ):
        cart = Cart.objects.create(user=regular_user)
        item = CartItem(cart=cart, variant=variant, quantity=0)
        with pytest.raises(DjangoValidationError):
            item.clean()


# ---------------------------------------------------------------------------
# Derived values (trusted server-side data only)
# ---------------------------------------------------------------------------


class TestDerivedValues:
    def test_total_quantity_and_subtotal(
        self, variant, variant_two, stock_record, stock_record_two, regular_user
    ):
        cart = Cart.objects.create(user=regular_user)
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        CartItem.objects.create(cart=cart, variant=variant_two, quantity=3)

        assert cart.total_quantity == 5
        assert cart.subtotal == Decimal("600.00")  # 2*120 + 3*120

    def test_variant_price_override_used_for_pricing(
        self, priced_variant, priced_stock_record, regular_user
    ):
        """Effective price honours the variant-level price override."""
        cart = Cart.objects.create(user=regular_user)
        item = CartItem.objects.create(cart=cart, variant=priced_variant, quantity=2)
        assert item.unit_price == Decimal("155.50")
        assert item.line_total == Decimal("311.00")

    def test_missing_stock_record_means_zero_availability(
        self, variant, regular_user
    ):
        """A variant without a StockRecord is treated as unavailable."""
        cart = Cart.objects.create(user=regular_user)
        item = CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        assert item.available_quantity == 0
        assert item.is_available is False
        assert item.has_sufficient_stock is False

    def test_has_stock_conflicts_flags_shortfall(
        self, variant, stock_record, regular_user
    ):
        """Cart-level conflict indicator reflects staged vs available units."""
        cart = Cart.objects.create(user=regular_user)
        item = CartItem.objects.create(cart=cart, variant=variant, quantity=10)
        assert item.has_sufficient_stock is True
        assert cart.has_stock_conflicts is False

        # Reduce available stock independently (e.g., stock sold elsewhere);
        # the cart row is unchanged, but the conflict must now be flagged.
        stock_record.quantity_reserved = 3
        stock_record.save(update_fields=["quantity_reserved"])

        assert item.available_quantity == 7
        assert item.has_sufficient_stock is False
        assert cart.has_stock_conflicts is True

    def test_clearing_cart_items_cascades_from_cart_deletion(
        self, variant, stock_record, regular_user
    ):
        cart = Cart.objects.create(user=regular_user)
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        cart.delete()
        assert CartItem.objects.count() == 0

    def test_deleting_variant_removes_cart_items(
        self, variant, stock_record, regular_user
    ):
        """Variant deletion also cleans up dependent cart lines (CASCADE)."""
        cart = Cart.objects.create(user=regular_user)
        CartItem.objects.create(cart=cart, variant=variant, quantity=1)
        variant.delete()
        assert CartItem.objects.count() == 0
