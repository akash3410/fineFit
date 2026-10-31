"""
Shared fixtures for cart domain tests.

Provides users, catalog seed data (products/variants), inventory balances,
and API clients — including a guest-flow helper that exercises real
Django sessions and CSRF exchanges.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import StockRecord

User = get_user_model()

GUEST_SESSION_KEY = "guest-session-key-for-tests-0123456789abcdef"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="shopper@example.com", password="ShopperPass1!"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@example.com", password="OtherPass1!"
    )


# ---------------------------------------------------------------------------
# Catalog seed data
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return Category.objects.create(name="Apparel", slug="apparel")


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        category=category,
        title="Silk Slip Dress",
        slug="silk-slip-dress",
        base_price="120.00",
        is_published=True,
    )


@pytest.fixture
def draft_product(db, category):
    return Product.objects.create(
        category=category,
        title="Secret Draft Dress",
        slug="secret-draft-dress",
        base_price="99.00",
        is_published=False,
    )


@pytest.fixture
def variant(db, product):
    return ProductVariant.objects.create(
        product=product,
        sku="SSD-BLK-M",
        size="M",
        color_name="Black",
        color_code="#000000",
    )


@pytest.fixture
def variant_two(db, product):
    return ProductVariant.objects.create(
        product=product,
        sku="SSD-RED-L",
        size="L",
        color_name="Red",
        color_code="#FF0000",
    )


@pytest.fixture
def inactive_variant(db, product):
    return ProductVariant.objects.create(
        product=product,
        sku="SSD-BLK-XS",
        size="XS",
        color_name="Black",
        color_code="#000000",
        is_active=False,
    )


@pytest.fixture
def draft_variant(db, draft_product):
    return ProductVariant.objects.create(
        product=draft_product,
        sku="SECRET-BLK-M",
        size="M",
        color_name="Black",
    )


@pytest.fixture
def priced_variant(db, product):
    """A variant with a price override, to verify variant-level pricing."""
    return ProductVariant.objects.create(
        product=product,
        sku="SSD-GOLD-XL",
        size="XL",
        color_name="Gold",
        price_override="155.50",
    )


@pytest.fixture
def empty_stock_variant(db, product):
    """An active variant of a published product with zero stock on hand."""
    return ProductVariant.objects.create(
        product=product,
        sku="SSD-BLK-S",
        size="S",
        color_name="Black",
    )


@pytest.fixture
def zero_stock_record(db, empty_stock_variant):
    return StockRecord.objects.create(
        variant=empty_stock_variant,
        quantity_on_hand=0,
        quantity_reserved=0,
    )


@pytest.fixture
def stock_record(db, variant):
    return StockRecord.objects.create(
        variant=variant,
        quantity_on_hand=10,
        quantity_reserved=0,
    )


@pytest.fixture
def stock_record_two(db, variant_two):
    return StockRecord.objects.create(
        variant=variant_two,
        quantity_on_hand=10,
        quantity_reserved=0,
    )


@pytest.fixture
def priced_stock_record(db, priced_variant):
    return StockRecord.objects.create(
        variant=priced_variant,
        quantity_on_hand=5,
        quantity_reserved=0,
    )


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_client():
    """Guest client WITHOUT CSRF enforcement (token flow tested explicitly)."""
    return APIClient()


@pytest.fixture
def strict_csrf_client():
    """Guest client WITH CSRF middleware enforcement enabled."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def user_client(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


# ---------------------------------------------------------------------------
# Guest session helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def guest_session(anon_client):
    """Creates a real guest session for a client; returns the session key."""
    from django.contrib.sessions.backends.db import SessionStore

    def _create(client=None):
        session = SessionStore()
        session.create()
        (client or anon_client).cookies["sessionid"] = session.session_key
        return session.session_key

    return _create


def obtain_csrf_token(client) -> str:
    """Fetch a CSRF cookie + token through the public CSRF endpoint."""
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200, response.content
    cookie = response.cookies.get("csrftoken")
    assert cookie is not None
    return cookie.value


@pytest.fixture
def csrf_for():
    """Function that obtains a CSRF token + cookie for a given client."""
    return obtain_csrf_token
