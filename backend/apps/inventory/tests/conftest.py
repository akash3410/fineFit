"""
Shared fixtures for inventory domain tests.
"""

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import StockMovement, StockRecord

User = get_user_model()


def _grant_inventory_perms(user, codenames):
    perms = Permission.objects.filter(
        content_type__app_label="inventory",
        codename__in=codenames,
    )
    user.user_permissions.add(*perms)


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="customer@example.com",
        password="ValidPassword123!",
        first_name="Jane",
        last_name="Shopper",
    )


@pytest.fixture
def staff_no_perms(db):
    user = User.objects.create_user(
        email="staff_noperms@example.com",
        password="ValidPassword123!",
        is_staff=True,
    )
    return user


@pytest.fixture
def inventory_viewer(db):
    user = User.objects.create_user(
        email="viewer@example.com",
        password="ValidPassword123!",
        is_staff=True,
    )
    _grant_inventory_perms(
        user,
        [
            "view_stockrecord",
            "view_stockmovement",
        ],
    )
    return user


@pytest.fixture
def inventory_manager(db):
    user = User.objects.create_user(
        email="manager@example.com",
        password="ValidPassword123!",
        is_staff=True,
    )
    _grant_inventory_perms(
        user,
        [
            "view_stockrecord",
            "add_stockrecord",
            "change_stockrecord",
            "delete_stockrecord",
            "view_stockmovement",
        ],
    )
    return user


@pytest.fixture
def category(db):
    return Category.objects.create(name="Apparel", slug="apparel")


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        title="Silk Slip Dress",
        slug="silk-slip-dress",
        category=category,
        base_price=Decimal("120.00"),
        is_published=True,
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
def stock_record(db, variant):
    return StockRecord.objects.create(
        variant=variant,
        quantity_on_hand=20,
        quantity_reserved=5,
        low_stock_threshold=5,
    )


# ---------------------------------------------------------------------------
# API Clients
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def user_client(regular_user):
    client = APIClient()
    client.force_authenticate(user=regular_user)
    return client


@pytest.fixture
def staff_no_perms_client(staff_no_perms):
    client = APIClient()
    client.force_authenticate(user=staff_no_perms)
    return client


@pytest.fixture
def viewer_client(inventory_viewer):
    client = APIClient()
    client.force_authenticate(user=inventory_viewer)
    return client


@pytest.fixture
def manager_client(inventory_manager):
    client = APIClient()
    client.force_authenticate(user=inventory_manager)
    return client

