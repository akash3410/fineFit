"""
Staff management API tests: authorization, CRUD, and payload validation.

Confirms that model permissions (not merely ``is_staff``) gate writes, that
drafts require the explicit view permission to list, and that invalid payloads
are rejected server-side.
"""

import pytest
from django.urls import reverse

from apps.catalog.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db


def _manage_url(basename, pk=None):
    base = reverse(f"manage-{basename}-list")
    if pk is not None:
        return f"{base}{pk}/"
    return base


class TestAuthorization:
    def test_anonymous_get_is_unauthenticated(self, anon_client, product):
        response = anon_client.get(_manage_url("product"))
        assert response.status_code in (401, 403)

    def test_anonymous_cannot_create(self, anon_client, category):
        response = anon_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "X", "base_price": "10.00"},
        )
        assert response.status_code in (401, 403)

    def test_staff_without_perms_cannot_list(self, staff_no_perms_client):
        response = staff_no_perms_client.get(_manage_url("product"))
        assert response.status_code == 403

    def test_staff_without_perms_cannot_create(self, staff_no_perms_client, category):
        response = staff_no_perms_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "X", "base_price": "10.00"},
        )
        assert response.status_code == 403

    def test_viewer_can_list_but_not_create(self, catalog_viewer_client, category, product):
        assert catalog_viewer_client.get(_manage_url("product")).status_code == 200
        response = catalog_viewer_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "Y", "base_price": "10.00"},
        )
        assert response.status_code == 403

    def test_viewer_sees_drafts_via_manage(self, catalog_viewer_client, draft_product):
        response = catalog_viewer_client.get(_manage_url("product"))
        slugs = [p["slug"] for p in response.data]  # manage list is not paginated
        assert "secret-draft-coat" in slugs


class TestProductCrud:
    def test_manager_creates_product(self, catalog_manager_client, category):
        response = catalog_manager_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "New Coat", "base_price": "120.00"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert Product.objects.filter(title="New Coat").exists()

    def test_manager_updates_product(self, catalog_manager_client, product):
        response = catalog_manager_client.patch(
            _manage_url("product", product.pk),
            {"base_price": "250.00"},
            content_type="application/json",
        )
        assert response.status_code == 200
        product.refresh_from_db()
        assert str(product.base_price) == "250.00"

    def test_manager_deletes_product(self, catalog_manager_client, product):
        response = catalog_manager_client.delete(_manage_url("product", product.pk))
        assert response.status_code == 204
        assert not Product.objects.filter(pk=product.pk).exists()

    def test_nested_variants_created_with_product(self, catalog_manager_client, category):
        payload = {
            "category": category.pk,
            "title": "Bundle",
            "base_price": "100.00",
            "variants": [
                {"sku": "BUNDLE-M", "size": "M"},
                {"sku": "BUNDLE-L", "size": "L"},
            ],
        }
        response = catalog_manager_client.post(
            _manage_url("product"), payload, content_type="application/json"
        )
        assert response.status_code == 201
        product = Product.objects.get(title="Bundle")
        assert product.variants.count() == 2

    def test_nested_variants_atomic_rollback(self, catalog_manager_client, category):
        """An invalid nested variant must roll back the whole product creation."""
        payload = {
            "category": category.pk,
            "title": "Atomic",
            "base_price": "100.00",
            "variants": [
                {"sku": "ATOMIC-OK", "size": "M"},
                {"sku": "ATOMIC-DUP", "size": "M"},  # duplicate size+color -> invalid
            ],
        }
        response = catalog_manager_client.post(
            _manage_url("product"), payload, content_type="application/json"
        )
        assert response.status_code == 400
        assert not Product.objects.filter(title="Atomic").exists()


class TestValidation:
    def test_negative_base_price_rejected(self, catalog_manager_client, category):
        response = catalog_manager_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "Bad", "base_price": "-5.00"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "base_price" in response.data

    def test_duplicate_sku_rejected(self, catalog_manager_client, product, variant):
        response = catalog_manager_client.post(
            _manage_url("variant"),
            {"product": product.pk, "sku": variant.sku},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "sku" in response.data

    def test_invalid_color_code_rejected(self, catalog_manager_client, product):
        response = catalog_manager_client.post(
            _manage_url("variant"),
            {"product": product.pk, "sku": "COLORBAD", "color_code": "blue"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "color_code" in response.data


class TestCategoryCrud:
    def test_manager_creates_category(self, catalog_manager_client):
        response = catalog_manager_client.post(
            _manage_url("category"),
            {"name": "Footwear", "slug": "footwear"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert Category.objects.filter(slug="footwear").exists()

    def test_category_parent_cycle_rejected(self, catalog_manager_client, category, child_category):
        response = catalog_manager_client.patch(
            _manage_url("category", category.pk),
            {"parent": child_category.pk},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "parent" in response.data


class TestVariantCrud:
    def test_manager_creates_variant(self, catalog_manager_client, product):
        response = catalog_manager_client.post(
            _manage_url("variant"),
            {"product": product.pk, "sku": "MANAGED-1", "size": "S"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert ProductVariant.objects.filter(sku="MANAGED-1").exists()
