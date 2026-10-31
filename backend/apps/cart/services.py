"""
CartService: transactional business operations for the shopping cart.

Policy boundary (ADR-010 Option B — accepted)
---------------------------------------------
Stock is NOT reserved when an item enters a cart. Every availability check
below is *advisory only*: it reads the ``apps.inventory`` source of truth
(``StockRecord``) but never reserves, decrements, or mutates stock in any way.
Availability is re-validated at checkout (Phase 4B) because stock may change
while items sit in a cart.

This service never writes to ``StockRecord`` or ``StockMovement``. The only
inventory interaction is reading ``variant.stock_record.available_quantity``.

Trust boundary
--------------
All quantities and identifiers are validated server-side; prices, subtotals
and availability are always computed from trusted catalog/inventory rows.
Client-supplied prices, owner IDs or session keys are never trusted.
"""

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import ProductVariant

from .exceptions import (
    CartItemNotFoundError,
    CartValidationError,
)
from .models import Cart, CartItem

#: Upper bound of units per single cart line (guards against abuse; not stock).
MAX_QUANTITY_PER_ITEM = 99


class CartService:
    """Service layer for cart lifecycle and line-item operations."""

    # ------------------------------------------------------------------
    # Cart resolution / ownership
    # ------------------------------------------------------------------
    @classmethod
    def get_or_create_cart(cls, user=None, session_key: str | None = None) -> Cart:
        """
        Return the active cart for the resolved owner, creating it if needed.

        Ownership rules:
          - ``user`` provided  -> the (single) cart of that customer.
          - ``session_key``    -> the (single) cart tied to the guest session.
          - Both               -> forbidden (callers must resolve one owner).
          - Neither            -> forbidden.

        Database constraints guarantee at most one active cart per owner.
        """
        if user is not None and session_key:
            raise CartValidationError(
                "A cart cannot be resolved for both a user and a guest session."
            )
        if user is not None:
            cart, _ = Cart.objects.get_or_create(user=user)
            return cart
        if session_key:
            cart, _ = Cart.objects.get_or_create(session_key=session_key)
            return cart
        raise CartValidationError("A cart requires a user or a guest session.")

    @classmethod
    def get_cart(cls, user=None, session_key: str | None = None) -> Cart | None:
        """Return the active cart for the owner, or None when none exists."""
        if user is not None and session_key:
            raise CartValidationError(
                "A cart cannot be resolved for both a user and a guest session."
            )
        if user is not None:
            return Cart.objects.for_user(user).first()
        if session_key:
            return Cart.objects.for_guest_session(session_key).first()
        raise CartValidationError("A cart requires a user or a guest session.")

    # ------------------------------------------------------------------
    # Line item operations (availability checks are advisory, never reserving)
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def add_item(
        cls,
        cart: Cart,
        variant_or_id: ProductVariant | uuid.UUID | str,
        quantity: int = 1,
    ) -> Cart:
        """
        Add a quantity of a variant to the cart, merging into an existing line.

        Validation performed server-side:
          - Variant must exist, be active, and belong to a published product.
          - Quantity must be a positive integer (capped at MAX_QUANTITY_PER_ITEM).
          - Combined quantity must not exceed currently available stock
            (advisory check; a missing StockRecord means unavailable).
        """
        variant = cls._resolve_purchasable_variant(variant_or_id)
        quantity = cls._validate_quantity(quantity)

        # Re-read inside the transaction to avoid races between concurrent
        # adds of the same variant (DB unique constraint is the backstop).
        stock_record = getattr(variant, "stock_record", None)
        if stock_record is None:
            raise CartValidationError(
                f"Variant '{variant.sku}' is currently unavailable."
            )
        available = stock_record.available_quantity

        item = cart.items.filter(variant_id=variant.id).first()
        new_quantity = quantity + (item.quantity if item else 0)
        if available < new_quantity:
            current = item.quantity if item else 0
            raise CartValidationError(
                f"Only {available} unit(s) of '{variant.sku}' currently available; "
                f"requested {quantity} more on top of {current}."
            )

        if item is None:
            try:
                item = CartItem.objects.create(
                    cart=cart, variant=variant, quantity=new_quantity
                )
            except IntegrityError:
                # Concurrent add created the line first: merge into it.
                item = cart.items.get(variant_id=variant.id)
                item.quantity = new_quantity
                item.full_clean()
                item.save(update_fields=["quantity", "updated_at"])
        else:
            item.quantity = new_quantity
            item.full_clean()
            item.save(update_fields=["quantity", "updated_at"])

        cart.refresh_from_db(fields=["updated_at"])
        return cart

    @classmethod
    @transaction.atomic
    def update_item_quantity(
        cls,
        cart: Cart,
        identifier: str | int,
        quantity: int,
    ) -> Cart:
        """
        Set the quantity of an existing cart line.

        Availability is re-checked on EVERY update (advisory; still no
        reservation). Concurrent stock changes may reduce availability before
        checkout — Phase 4B re-validates authoritatively there.
        """
        item = cls._resolve_cart_item(cart, identifier)
        quantity = cls._validate_quantity(quantity)

        stock_record = getattr(item.variant, "stock_record", None)
        if stock_record is None:
            raise CartValidationError(
                f"Variant '{item.variant.sku}' is currently unavailable."
            )
        available = stock_record.available_quantity
        if available < quantity:
            raise CartValidationError(
                f"Only {available} unit(s) of '{item.variant.sku}' currently available."
            )

        item.quantity = quantity
        item.full_clean()
        item.save(update_fields=["quantity", "updated_at"])

        cart.refresh_from_db(fields=["updated_at"])
        return cart

    @classmethod
    @transaction.atomic
    def remove_item(cls, cart: Cart, identifier: str | int) -> Cart:
        """Remove a line item from the cart (stock state is untouched)."""
        item = cls._resolve_cart_item(cart, identifier)
        item.delete()
        cart.refresh_from_db(fields=["updated_at"])
        return cart

    @classmethod
    @transaction.atomic
    def clear_cart(cls, cart: Cart) -> Cart:
        """Remove every line item from the cart (the cart itself persists)."""
        cart.items.all().delete()
        cart.refresh_from_db(fields=["updated_at"])
        return cart

    # ------------------------------------------------------------------
    # Guest -> user merge (invoked from the login flow)
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def merge_guest_cart_into_user_cart(
        cls,
        guest_session_key: str | None,
        user,
    ) -> tuple[Cart, list[dict]]:
        """
        Merge the cart of a guest session into the authenticated customer's cart.

        Called by the accounts login view AFTER authentication succeeds and
        BEFORE relying on the (possibly rotated) session key. The guest
        session key must be captured by the caller prior to ``django.contrib
        .auth.login()`` rotating the session.

        Rules:
          - Runs in a single database transaction.
          - Duplicate variants are combined (quantities added); no line is
            silently discarded.
          - No stock is reserved during the merge.
          - Availability conflicts are REPORTED (not silently dropped): rows
            whose combined quantity exceeds current availability stay in the
            cart and are listed in ``conflicts`` so the customer can review
            the cart before checkout.
          - Unpublished products / inactive variants are also flagged rather
            than deleted, preserving customer intent.
          - The guest cart row is removed afterwards; the Django session
            itself is left untouched.

        Returns ``(user_cart, conflicts)`` where ``conflicts`` is a list of
        dicts describing availability problems for storefront messaging.
        """
        if not guest_session_key:
            # No guest cart possible; ensure the customer has an active cart.
            return cls.get_or_create_cart(user=user), []

        guest_cart = (
            Cart.objects.for_guest_session(guest_session_key)
            .prefetch_related("items__variant__product")
            .first()
        )
        if guest_cart is None:
            return cls.get_or_create_cart(user=user), []

        user_cart = cls.get_or_create_cart(user=user)
        conflicts: list[dict] = []

        user_items = {
            item.variant_id: item for item in user_cart.items.select_related("variant")
        }
        guest_items = list(
            guest_cart.items.select_related("variant__product").order_by("created_at")
        )

        for guest_item in guest_items:
            variant: ProductVariant = guest_item.variant
            existing = user_items.get(variant.id)
            target = existing if existing is not None else CartItem(cart=user_cart)
            target.variant = variant
            # Combine quantities; never discard the customer's staged amount.
            combined = guest_item.quantity + (existing.quantity if existing else 0)

            stock_record = getattr(variant, "stock_record", None)
            if not variant.product.is_published or not variant.is_active:
                conflicts.append(
                    {
                        "variant_id": str(variant.id),
                        "sku": variant.sku,
                        "quantity": combined,
                        "available_quantity": 0,
                        "reason": "VARIANT_UNAVAILABLE",
                    }
                )
            elif stock_record is None:
                conflicts.append(
                    {
                        "variant_id": str(variant.id),
                        "sku": variant.sku,
                        "quantity": combined,
                        "available_quantity": 0,
                        "reason": "OUT_OF_STOCK",
                    }
                )
            elif stock_record.available_quantity < combined:
                conflicts.append(
                    {
                        "variant_id": str(variant.id),
                        "sku": variant.sku,
                        "quantity": combined,
                        "available_quantity": stock_record.available_quantity,
                        "reason": "INSUFFICIENT_STOCK",
                    }
                )

            target.quantity = combined
            try:
                target.full_clean()
                target.save()
            except DjangoValidationError as err:
                raise CartValidationError(
                    f"Could not merge variant '{variant.sku}' into your cart."
                ) from err
            user_items[variant.id] = target

        # Drain the guest cart (items cascade-delete); session untouched.
        guest_cart.delete()

        user_cart.refresh_from_db(fields=["updated_at"])
        return user_cart, conflicts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_purchasable_variant(
        variant_or_id: ProductVariant | uuid.UUID | str,
    ) -> ProductVariant:
        """
        Fetch the variant for a purchasable add/update attempt.

        A variant may be added only when its product is published and the
        variant is active. Anything else is a validation error.
        """
        if isinstance(variant_or_id, ProductVariant):
            variant_id = variant_or_id.id
        elif isinstance(variant_or_id, uuid.UUID):
            variant_id = variant_or_id
        else:
            try:
                variant_id = uuid.UUID(str(variant_or_id))
            except (ValueError, TypeError) as err:
                raise CartValidationError("Invalid variant identifier.") from err

        variant = (
            ProductVariant.objects.select_related("product", "stock_record")
            .filter(id=variant_id)
            .first()
        )
        if variant is None:
            raise CartValidationError("Variant not found.")
        if not variant.is_active or not variant.product.is_published:
            raise CartValidationError(
                "This variant is not available for purchase."
            )
        return variant

    @staticmethod
    def _validate_quantity(quantity) -> int:
        """Validate a requested quantity (type, bounds; independent of stock)."""
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise CartValidationError("Quantity must be a whole number.")
        if quantity < 1:
            raise CartValidationError("Quantity must be at least 1.")
        if quantity > MAX_QUANTITY_PER_ITEM:
            raise CartValidationError(
                f"Quantity cannot exceed {MAX_QUANTITY_PER_ITEM} per item."
            )
        return quantity

    @staticmethod
    def _resolve_cart_item(cart: Cart, identifier: str | int) -> CartItem:
        """
        Locate a cart line by its primary key or by variant identifier.

        The item must belong to ``cart``; lookups never leak other users'
        carts (tenant filtering by the caller's cart reference).
        """
        item = None
        try:
            variant_uuid = uuid.UUID(str(identifier))
            item = cart.items.select_related("variant", "variant__product").filter(
                variant_id=variant_uuid
            ).first()
        except ValueError:
            item = None

        if item is None:
            try:
                item_pk = int(identifier)
            except (ValueError, TypeError) as err:
                raise CartItemNotFoundError("Cart item not found.") from err
            item = cart.items.select_related("variant", "variant__product").filter(
                pk=item_pk
            ).first()

        if item is None:
            raise CartItemNotFoundError("Cart item not found.")
        return item
