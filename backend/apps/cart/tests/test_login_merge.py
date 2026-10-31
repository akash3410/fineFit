"""
PostgreSQL-backed tests for guest-to-user cart merge integrated with the
login flow.

Key focus: the guest session key must be captured BEFORE Django's
``login()`` rotates it (session-fixation protection), the merge must survive
session rotation, and failed logins must never touch the guest cart.
"""

import pytest
from django.test import Client

from apps.cart.models import Cart, CartItem
from apps.cart.services import CartService

pytestmark = pytest.mark.django_db

CART_URL = "/api/v1/cart/"
ITEMS_URL = "/api/v1/cart/items/"
LOGIN_URL = "/api/v1/auth/login/"


def _login(client, email, password, csrf_token):
    return client.post(
        LOGIN_URL,
        data={"email": email, "password": password},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )


class TestGuestCartSurvivalAroundLogin:
    def test_successful_login_merges_guest_cart(
        self, csrf_for, variant, stock_record, regular_user
    ):
        """Guest adds items -> logs in -> items are in the customer cart."""
        client = Client(enforce_csrf_checks=True)
        token = csrf_for(client)

        added = client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 2},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert added.status_code == 201, added.content

        response = _login(client, "shopper@example.com", "ShopperPass1!", token)
        assert response.status_code == 200

        cart = client.get(CART_URL)
        assert cart.status_code == 200
        data = cart.json()
        assert data["total_quantity"] == 2
        assert data["items"][0]["variant"]["sku"] == variant.sku

        # The pre-login guest cart row was consumed by the merge...
        assert not Cart.objects.filter(
            session_key=client.cookies["sessionid"].value
        ).exists()
        # ...and exactly one active user cart exists.
        assert Cart.objects.filter(user=regular_user).count() == 1

    def test_session_rotation_does_not_lose_guest_cart(
        self, csrf_for, variant, stock_record, regular_user
    ):
        """
        login() rotates the session key; the merge must use the key captured
        BEFORE rotation, so nothing is lost.
        """
        client = Client(enforce_csrf_checks=True)
        token = csrf_for(client)

        added = client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 3},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert added.status_code == 201
        session_key_before_login = client.cookies["sessionid"].value
        visitor = CartService.get_cart(session_key=session_key_before_login)
        guest_cart_id = visitor.id
        response = _login(client, "shopper@example.com", "ShopperPass1!", token)
        assert response.status_code == 200

        session_key_after_login = client.cookies["sessionid"].value
        assert session_key_after_login != session_key_before_login

        cart = client.get(CART_URL).json()
        assert cart["total_quantity"] == 3
        assert not Cart.objects.filter(id=guest_cart_id).exists()

    def test_failed_login_does_not_modify_guest_cart(
        self, csrf_for, variant, stock_record
    ):
        """A failed login attempt must leave the guest cart completely intact."""
        client = Client(enforce_csrf_checks=True)
        token = csrf_for(client)

        added = client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 2},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert added.status_code == 201
        cart_before = added.json()

        failed = _login(client, "shopper@example.com", "WrongPassword!", token)
        assert failed.status_code == 401

        cart_after = client.get(CART_URL).json()
        assert cart_after["id"] == cart_before["id"]
        assert cart_after["total_quantity"] == 2
        # Still a guest cart; no customer cart was created or modified.
        assert Cart.objects.filter(user__email="shopper@example.com").count() == 0

    def test_merge_response_reports_conflicts_on_login(
        self, csrf_for, variant, stock_record, regular_user
    ):
        """Login payload includes merge metadata and stock conflicts when any."""
        client = Client(enforce_csrf_checks=True)
        token = csrf_for(client)
        added = client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 2},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert added.status_code == 201

        # Shrink availability after staging (stock changed while in cart).
        stock_record.quantity_reserved = 9  # only 1 unit now available
        stock_record.save(update_fields=["quantity_reserved"])

        response = _login(client, "shopper@example.com", "ShopperPass1!", token)
        payload = response.json()
        assert payload["cart_merge"]["conflicts"][0]["reason"] == "INSUFFICIENT_STOCK"
        assert payload["cart_merge"]["total_quantity"] == 2

    def test_customer_with_existing_cart_gets_items_added(
        self, csrf_for, variant, variant_two, stock_record, stock_record_two, regular_user
    ):
        """
        A customer who already has a cart receives the guest items merged in;
        duplicate variants combine instead of colliding.
        """
        user_cart = CartService.get_or_create_cart(user=regular_user)
        CartService.add_item(user_cart, variant, quantity=1)

        client = Client(enforce_csrf_checks=True)
        token = csrf_for(client)
        guest_add = client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": 2},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert guest_add.status_code == 201

        client.post(
            ITEMS_URL,
            data={"variant_id": str(variant_two.id), "quantity": 1},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        response = _login(client, "shopper@example.com", "ShopperPass1!", token)
        assert response.status_code == 200

        cart = client.get(CART_URL).json()
        by_variant = {i["variant"]["sku"]: i["quantity"] for i in cart["items"]}
        assert by_variant[variant.sku] == 3  # combined 1 + 2
        assert by_variant[variant_two.sku] == 1
        assert Cart.objects.filter(user=regular_user).count() == 1
