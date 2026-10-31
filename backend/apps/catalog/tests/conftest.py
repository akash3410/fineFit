"""
Shared fixtures for catalog tests.

Provides users with granular model permissions, catalog seed data, and a helper
to generate valid in-memory image uploads for ``ImageField`` tests.
"""

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.catalog.models import Category, Product, ProductImage, ProductVariant

User = get_user_model()

CATALOG_MODELS = (Category, Product, ProductVariant, ProductImage)
ALL_CODENAMES = ("view", "add", "change", "delete")


def _grant(user, model, codenames):
    perms = Permission.objects.filter(
        content_type__app_label="catalog",
        content_type__model=model._meta.model_name,
        codename__in=[f"{c}_{model._meta.model_name}" for c in codenames],
    )
    user.user_permissions.add(*perms)


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """
    Redirect upload storage to a per-test directory.

    pytest-django rolls the *database* back after each test, but any image
    files written during a request would otherwise remain in the real
    development ``MEDIA_ROOT`` forever as orphans. Pointing ``MEDIA_ROOT``
    (via the ``settings`` fixture) at ``tmp_path`` keeps the development
    media directory clean.
    """
    settings.MEDIA_ROOT = tmp_path / "media"


def make_image_file(name="test", image_format="PNG", size=(100, 100), color=(255, 0, 0)):
    """Return a ``SimpleUploadedFile`` containing a real generated image."""
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=image_format)
    buffer.seek(0)
    ext = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[image_format]
    content_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]
    return SimpleUploadedFile(f"{name}.{ext}", buffer.read(), content_type=content_type)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_client(db):
    return Client()


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(email="shopper@example.com", password="ShopperPass1!")


@pytest.fixture
def regular_client(regular_user):
    client = Client()
    client.force_login(regular_user)
    return client


@pytest.fixture
def staff_no_perms(db):
    """A staff user with NO catalog permissions (is_staff alone must not suffice)."""
    return User.objects.create_user(
        email="staff@example.com", password="StaffPass1!", is_staff=True
    )


@pytest.fixture
def staff_no_perms_client(staff_no_perms):
    client = Client()
    client.force_login(staff_no_perms)
    return client


@pytest.fixture
def catalog_manager(db):
    """User granted full catalog model permissions (view/add/change/delete)."""
    user = User.objects.create_user(
        email="manager@example.com", password="ManagerPass1!", is_staff=True
    )
    for model in CATALOG_MODELS:
        _grant(user, model, ALL_CODENAMES)
    return user


@pytest.fixture
def catalog_manager_client(catalog_manager):
    client = Client()
    client.force_login(catalog_manager)
    return client


@pytest.fixture
def catalog_viewer(db):
    """User granted only the view permission on catalog models."""
    user = User.objects.create_user(
        email="viewer@example.com", password="ViewerPass1!", is_staff=True
    )
    for model in CATALOG_MODELS:
        _grant(user, model, ("view",))
    return user


@pytest.fixture
def catalog_viewer_client(catalog_viewer):
    client = Client()
    client.force_login(catalog_viewer)
    return client


# ---------------------------------------------------------------------------
# Catalog seed data
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return Category.objects.create(name="Outerwear", slug="outerwear")


@pytest.fixture
def child_category(category):
    return Category.objects.create(name="Coats", slug="coats", parent=category)


@pytest.fixture
def inactive_category(db):
    return Category.objects.create(name="Archived", slug="archived", is_active=False)


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category,
        title="Aurora Wool Overcoat",
        slug="aurora-wool-overcoat",
        base_price="199.00",
        is_published=True,
    )


@pytest.fixture
def draft_product(category):
    return Product.objects.create(
        category=category,
        title="Secret Draft Coat",
        slug="secret-draft-coat",
        base_price="99.00",
        is_published=False,
    )


@pytest.fixture
def product_in_inactive_category(inactive_category):
    return Product.objects.create(
        category=inactive_category,
        title="Hidden Category Coat",
        slug="hidden-category-coat",
        base_price="149.00",
        is_published=True,
    )


@pytest.fixture
def variant(product):
    return ProductVariant.objects.create(
        product=product,
        sku="AURORA-M-BLK",
        size="M",
        color_name="Midnight Black",
        color_code="#1F2937",
    )
