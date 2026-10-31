import pytest
from django.urls import reverse

from apps.catalog.models import Category, Product, ProductImage, ProductVariant
from apps.catalog.tests.conftest import make_image_file

pytestmark = pytest.mark.django_db


def _manage_url(basename, pk=None):
    base = reverse(f"manage-{basename}-list")
    if pk is not None:
        return f"{base}{pk}/"
    return base


class TestNestedVariantParentAssignment:
    def test_nested_variants_belong_to_new_parent(self, catalog_manager_client, category):
        payload = {
            "category": category.pk,
            "title": "Nested Parent",
            "base_price": "100.00",
            "variants": [
                {"sku": "NEST-M", "size": "M"},
                {"sku": "NEST-L", "size": "L"},
            ],
        }
        response = catalog_manager_client.post(
            _manage_url("product"), payload, content_type="application/json"
        )
        assert response.status_code == 201
        product = Product.objects.get(title="Nested Parent")
        variants = ProductVariant.objects.filter(sku__in=["NEST-M", "NEST-L"])
        assert variants.count() == 2
        assert all(v.product_id == product.pk for v in variants)

    def test_nested_payload_cannot_attach_to_unrelated_product(
        self, catalog_manager_client, category
    ):
        other = Product.objects.create(
            category=category, title="Other", slug="other", base_price="50.00"
        )
        payload = {
            "category": category.pk,
            "title": "Nested Safe",
            "base_price": "100.00",
            "variants": [
                {"sku": "SAFE-M", "size": "M", "product": other.pk},
            ],
        }
        response = catalog_manager_client.post(
            _manage_url("product"), payload, content_type="application/json"
        )
        assert response.status_code == 201
        product = Product.objects.get(title="Nested Safe")
        variant = ProductVariant.objects.get(sku="SAFE-M")
        assert variant.product_id == product.pk
        assert variant.product_id != other.pk

    def test_standalone_variant_requires_product(self, catalog_manager_client):
        response = catalog_manager_client.post(
            _manage_url("variant"),
            {"sku": "NO-PRODUCT", "size": "M"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "product" in response.data

    def test_standalone_variant_rejects_invalid_product(self, catalog_manager_client):
        response = catalog_manager_client.post(
            _manage_url("variant"),
            {"product": 999999, "sku": "BAD-PRODUCT", "size": "M"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "product" in response.data


class TestAtomicity:
    def test_invalid_nested_variant_leaves_no_partial_records(
        self, catalog_manager_client, category
    ):
        payload = {
            "category": category.pk,
            "title": "Atomic Test",
            "base_price": "100.00",
            "variants": [
                {"sku": "ATOMIC-OK", "size": "M"},
                {"sku": "ATOMIC-DUP", "size": "M"},
            ],
        }
        response = catalog_manager_client.post(
            _manage_url("product"), payload, content_type="application/json"
        )
        assert response.status_code == 400
        assert not Product.objects.filter(title="Atomic Test").exists()
        assert not ProductVariant.objects.filter(sku__startswith="ATOMIC-").exists()


class TestAuthorizationExtended:
    def test_anonymous_cannot_update_or_delete(self, anon_client, product):
        assert anon_client.patch(
            _manage_url("product", product.pk), {"title": "X"}, content_type="application/json"
        ).status_code in (401, 403)
        assert anon_client.delete(_manage_url("product", product.pk)).status_code in (401, 403)

    def test_regular_user_cannot_write(self, regular_client, category):
        assert regular_client.post(
            _manage_url("product"),
            {"category": category.pk, "title": "X", "base_price": "10.00"},
            content_type="application/json",
        ).status_code == 403

    def test_staff_without_perms_cannot_update_or_delete(
        self, staff_no_perms_client, product
    ):
        assert staff_no_perms_client.patch(
            _manage_url("product", product.pk), {"title": "X"}, content_type="application/json"
        ).status_code == 403
        assert staff_no_perms_client.delete(_manage_url("product", product.pk)).status_code == 403

    def test_viewer_cannot_update_or_delete(self, catalog_viewer_client, product):
        assert catalog_viewer_client.patch(
            _manage_url("product", product.pk), {"title": "X"}, content_type="application/json"
        ).status_code == 403
        assert catalog_viewer_client.delete(_manage_url("product", product.pk)).status_code == 403


class TestUnpublishedIsolationExtended:
    def test_draft_excluded_from_search_and_filters(self, anon_client, category):
        draft = Product.objects.create(
            category=category, title="Draft Search", slug="draft-search", base_price="10.00", is_published=False
        )
        published = Product.objects.create(
            category=category, title="Published Search", slug="published-search", base_price="10.00", is_published=True
        )
        response = anon_client.get(reverse("product-list"), {"search": "Search"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert published.slug in slugs
        assert draft.slug not in slugs

    def test_draft_cannot_be_retrieved_by_slug(self, anon_client, draft_product):
        response = anon_client.get(reverse("product-detail", kwargs={"slug": draft_product.slug}))
        assert response.status_code == 404


class TestVariantImageIntegrity:
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

    def test_image_primary_uniqueness(self, catalog_manager_client, product):
        first = catalog_manager_client.post(
            _manage_url("image"),
            {"product": product.pk, "image": make_image_file(), "is_primary": True},
            format="multipart",
        )
        assert first.status_code == 201
        second = catalog_manager_client.post(
            _manage_url("image"),
            {"product": product.pk, "image": make_image_file(name="second"), "is_primary": True},
            format="multipart",
        )
        assert second.status_code == 400

    def test_image_ordering(self, anon_client, product):
        img2 = ProductImage.objects.create(
            product=product, image=make_image_file(name="two"), display_order=2
        )
        img1 = ProductImage.objects.create(
            product=product, image=make_image_file(name="one"), display_order=1
        )
        response = anon_client.get(reverse("product-detail", kwargs={"slug": product.slug}))
        # detail includes images; verify ordering if exposed
        if "images" in response.data:
            orders = [img["display_order"] for img in response.data["images"]]
            assert orders == sorted(orders)
