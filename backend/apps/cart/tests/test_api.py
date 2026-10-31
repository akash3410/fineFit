"""
PostgreSQL-backed API tests for the versioned cart endpoints.

Covers: guest cart operations, authenticated customer operations, cross-user
isolation, unauthorized/forbidden access, validation errors, guest CSRF
enforcement, session ownership, and add/update/remove/clear behaviour.
"""

import pytest
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem

pytestmark = pytest.mark.django_db

CART_URL = "/api/v1/cart/"
ITEMS_URL = "/api/v1/cart/items/"


def _add_payload(variant, quantity=1):
    return {"variant_id": str(variant.id), "quantity": quantity}


class TestGuestCartOperations:
    def test_get_empty_cart_creates_guest_cart(self, anon_client):
        response = anon_client.get(CART_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["total_quantity"] == 0
        assert data["items"] == []
        assert "session_key" not in data  # session identifiers are never exposed
        assert not any("session" in key for key in data.keys())

    def test_guest_add_update_remove_flow(
        self, anon_client, csrf_for, variant, stock_record
    ):
        token = csrf_for(anon_client)

        add = anon_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 2),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert add.status_code == 201, add.content
        cart = add.json()
        assert cart["total_quantity"] == 2

        item_id = cart["items"][0]["id"]
        assert cart["items"][0]["quantity"] == 2
        assert cart["items"][0]["unit_price"] == "120.00"
        assert cart["items"][0]["line_total"] == "240.00"

        # Same guest session: GET returns the same cart (session ownership).
        fetched = anon_client.get(CART_URL)
        assert fetched.json()["id"] == cart["id"]

        update = anon_client.patch(
            f"{ITEMS_URL}{item_id}/",
            data={"quantity": 3},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert update.status_code == 200
        assert update.json()["total_quantity"] == 3

        delete = anon_client.delete(
            f"{ITEMS_URL}{item_id}/", HTTP_X_CSRFTOKEN=token
        )
        assert delete.status_code == 200
        assert delete.json()["total_quantity"] == 0

    def test_guest_clear_via_delete_and_clear_endpoint(
        self, anon_client, csrf_for, variant, stock_record
    ):
        token = csrf_for(anon_client)
        assert anon_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code == 201

        cleared = anon_client.post("/api/v1/cart/clear/", HTTP_X_CSRFTOKEN=token)
        assert cleared.status_code == 200
        assert cleared.json()["total_quantity"] == 0

        assert anon_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code == 201
        cleared = anon_client.delete(CART_URL, HTTP_X_CSRFTOKEN=token)
        assert cleared.status_code == 200
        assert cleared.json()["total_quantity"] == 0

    def test_guest_csrf_enforcement_on_writes(
        self, strict_csrf_client, csrf_for, variant, stock_record
    ):
        """Guest POST/PATCH/DELETE REQUIRE CSRF; writes without a token are 403."""
        client = strict_csrf_client

        # Establish a guest session first.
        client.get(CART_URL)

        denied_add = client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
        )
        assert denied_add.status_code == 403
        assert "csrf" in denied_add.json()["detail"].lower() or "CSRF" in str(
            denied_add.json()["detail"]
        )

        # With a valid token the identical request succeeds.
        token = csrf_for(client)
        allowed_add = client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert allowed_add.status_code == 201

        item_id = allowed_add.json()["items"][0]["id"]
        denied_update = client.patch(
            f"{ITEMS_URL}{item_id}/",
            data={"quantity": 2},
            content_type="application/json",
        )
        assert denied_update.status_code == 403

        denied_delete = client.delete(f"{ITEMS_URL}{item_id}/")
        assert denied_delete.status_code == 403

    def test_guest_csrf_invalid_token_rejected(
        self, strict_csrf_client, csrf_for, variant, stock_record
    ):
        client = strict_csrf_client
        client.get(CART_URL)
        token = csrf_for(client)
        rejected = client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
            HTTP_X_CSRFTOKEN="tampered-token",
        )
        assert rejected.status_code == 403

    def test_guest_isolation_between_sessions(
        self, anon_client, csrf_for, other_user, variant, stock_record
    ):
        """Another guest session (different session cookie) sees a separate cart."""
        token = csrf_for(anon_client)
        created = anon_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 2),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        cart_id = created.json()["id"]

        fresh_guest = APIClient()
        other_cart = fresh_guest.get(CART_URL)
        assert other_cart.status_code == 200
        assert other_cart.json()["id"] != cart_id
        assert other_cart.json()["total_quantity"] == 0


class TestAuthenticatedCartOperations:
    def test_user_add_list_update_remove(
        self, user_client, variant, variant_two, stock_record, stock_record_two
    ):
        added = user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 2),
            content_type="application/json",
        )
        assert added.status_code == 201
        cart = added.json()
        assert cart["total_quantity"] == 2
        assert cart["subtotal"] == "240.00"

        item_id = cart["items"][0]["id"]
        updated = user_client.patch(
            f"{ITEMS_URL}{item_id}/",
            data={"quantity": 5},
            content_type="application/json",
        )
        assert updated.status_code == 200
        assert updated.json()["total_quantity"] == 5
        assert updated.json()["subtotal"] == "600.00"
        # Stock conflict flags available in the response payload.
        assert updated.json()["has_stock_conflicts"] is False

        removed = user_client.delete(f"{ITEMS_URL}{item_id}/")
        assert removed.status_code == 200
        assert removed.json()["total_quantity"] == 0

    def test_user_get_cart_is_empty_and_persists_items(
        self, user_client, variant, stock_record
    ):
        first = user_client.get(CART_URL)
        assert first.status_code == 200
        cart_id = first.json()["id"]

        user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
        )
        again = user_client.get(CART_URL)
        assert again.status_code == 200
        assert again.json()["id"] == cart_id  # the single active user cart
        assert again.json()["total_quantity"] == 1

    def test_mutation_without_csrf_token_is_rejected_for_authenticated_users(
        self, variant, stock_record, regular_user
    ):
        """Authenticated writes also enforce CSRF (SessionAuthentication)."""
        client = APIClient(enforce_csrf_checks=True)
        # Log in with a plain Django test client (CSRF-safe exchange).
        from django.test import Client

        browser = Client(enforce_csrf_checks=True)
        csrf_token = browser.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        assert browser.post(
            "/api/v1/auth/login/",
            data={"email": "shopper@example.com", "password": "ShopperPass1!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        ).status_code == 200

        # Reuse the session cookies with the DRF client.
        for name in ("sessionid", "csrftoken"):
            if browser.cookies[name]:
                client.cookies[name] = browser.cookies[name].value

        denied = client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
        )
        assert denied.status_code == 403


class TestCrossUserIsolation:
    def test_user_cannot_read_or_modify_other_customers_cart(
        self,
        user_client,
        other_client,
        regular_user,
        other_user,
        variant,
        stock_record,
    ):
        """One customer may never touch another customer's cart."""
        other_added = other_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 2),
            content_type="application/json",
        )
        other_cart = other_added.json()
        other_item_id = other_cart["items"][0]["id"]
        other_cart_id = other_cart["id"]

        # My cart is empty and is a different cart.
        mine = user_client.get(CART_URL)
        assert mine.status_code == 200
        assert mine.json()["id"] != other_cart_id
        assert mine.json()["total_quantity"] == 0

        # Cannot update or remove the other customer's line.
        assert (
            user_client.patch(
                f"{ITEMS_URL}{other_item_id}/",
                data={"quantity": 1},
                content_type="application/json",
            ).status_code
            == 400
        )
        assert (
            user_client.delete(f"{ITEMS_URL}{other_item_id}/").status_code == 400
        )

        # The other customer's cart is unchanged (no leakage).
        other_cart_after = other_client.get(CART_URL)
        assert other_cart_after.json()["total_quantity"] == 2

    def test_user_clear_does_not_affect_other_users(
        self, user_client, other_client, variant, stock_record, variant_two, stock_record_two
    ):
        user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
        )
        other_client.post(
            ITEMS_URL,
            data=_add_payload(variant_two, 2),
            content_type="application/json",
        )
        cleared = user_client.delete(CART_URL)
        assert cleared.status_code == 200
        assert cleared.json()["total_quantity"] == 0
        assert other_client.get(CART_URL).json()["total_quantity"] == 2


class TestValidationErrors:
    def test_add_requires_variant_id(self, user_client, variant, stock_record):
        response = user_client.post(
            ITEMS_URL, data={}, content_type="application/json"
        )
        assert response.status_code == 400

    def test_add_rejects_huge_quantity(self, user_client, variant, stock_record):
        response = user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 101),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_add_rejects_non_numeric_quantity(self, user_client, variant, stock_record):
        response = user_client.post(
            ITEMS_URL,
            data={"variant_id": str(variant.id), "quantity": "two"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_add_rejects_zero_quantity(self, user_client, variant, stock_record):
        response = user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 0),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_add_unavailable_variant_returns_conflict_info(
        self, user_client, empty_stock_variant, zero_stock_record
    ):
        response = user_client.post(
            ITEMS_URL,
            data=_add_payload(empty_stock_variant, 1),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "Only 0 unit(s)" in response.json()["detail"]

    def test_add_exceeding_available_stock(
        self, user_client, variant, stock_record
    ):
        response = user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 11),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "Only 10" in response.json()["detail"]

    def test_update_requires_positive_quantity(
        self, user_client, variant, stock_record
    ):
        created = user_client.post(
            ITEMS_URL,
            data=_add_payload(variant, 1),
            content_type="application/json",
        ).json()
        item_id = created["items"][0]["id"]
        response = user_client.patch(
            f"{ITEMS_URL}{item_id}/",
            data={"quantity": 0},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_unknown_item(self, user_client):
        response = user_client.patch(
            f"{ITEMS_URL}123456/",
            data={"quantity": 1},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_put_not_allowed(self, user_client):
        response = user_client.put(
            f"{ITEMS_URL}1/", data={"quantity": 1}, content_type="application/json"
        )
        assert response.status_code == 405
