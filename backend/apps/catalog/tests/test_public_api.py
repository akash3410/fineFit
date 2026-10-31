"""
Public catalog API tests: visibility, search, filtering, sorting, pagination.

Confirms that anonymous visitors only ever see published products under active
categories, and that drafts/inactive data cannot leak through any surface.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestCategoryEndpoints:
    def test_lists_only_active_root_categories(self, anon_client, category, child_category, inactive_category):
        response = anon_client.get(reverse("category-list"))
        assert response.status_code == 200
        slugs = [c["slug"] for c in response.data["results"]] if "results" in response.data else [c["slug"] for c in response.data]
        assert "outerwear" in slugs
        assert "archived" not in slugs  # inactive hidden
        assert "coats" not in slugs  # child not at root

    def test_nested_children_included(self, anon_client, category, child_category):
        response = anon_client.get(reverse("category-list"))
        data = response.data
        results = data["results"] if "results" in data else data
        root = next(c for c in results if c["slug"] == "outerwear")
        assert any(ch["slug"] == "coats" for ch in root["children"])


class TestProductListVisibility:
    def test_shows_only_published(self, anon_client, product, draft_product):
        response = anon_client.get(reverse("product-list"))
        assert response.status_code == 200
        slugs = [p["slug"] for p in response.data["results"]]
        assert "aurora-wool-overcoat" in slugs
        assert "secret-draft-coat" not in slugs

    def test_hides_products_in_inactive_category(self, anon_client, product_in_inactive_category):
        response = anon_client.get(reverse("product-list"))
        slugs = [p["slug"] for p in response.data["results"]]
        assert "hidden-category-coat" not in slugs

    def test_exposes_primary_image(self, anon_client, product):
        from apps.catalog.models import ProductImage
        from apps.catalog.tests.conftest import make_image_file

        ProductImage.objects.create(product=product, image=make_image_file(), is_primary=True)
        response = anon_client.get(reverse("product-list"))
        results = response.data["results"]
        card = next(p for p in results if p["slug"] == product.slug)
        assert card["primary_image"] is not None
        assert card["primary_image"]["is_primary"] is True


class TestProductDetail:
    def test_returns_published_product(self, anon_client, product, variant):
        response = anon_client.get(reverse("product-detail", kwargs={"slug": product.slug}))
        assert response.status_code == 200
        assert response.data["slug"] == product.slug

    def test_draft_returns_404(self, anon_client, draft_product):
        response = anon_client.get(reverse("product-detail", kwargs={"slug": draft_product.slug}))
        assert response.status_code == 404

    def test_inactive_category_product_returns_404(self, anon_client, product_in_inactive_category):
        response = anon_client.get(
            reverse("product-detail", kwargs={"slug": product_in_inactive_category.slug})
        )
        assert response.status_code == 404

    def test_hides_inactive_variants(self, anon_client, product):
        from apps.catalog.models import ProductVariant

        active = ProductVariant.objects.create(product=product, sku="ACTIVE-1", size="M")
        ProductVariant.objects.create(product=product, sku="INACTIVE-1", size="L", is_active=False)
        response = anon_client.get(reverse("product-detail", kwargs={"slug": product.slug}))
        skus = [v["sku"] for v in response.data["variants"]]
        assert "ACTIVE-1" in skus
        assert "INACTIVE-1" not in skus

    def test_variant_effective_price(self, anon_client, product):
        from apps.catalog.models import ProductVariant

        ProductVariant.objects.create(product=product, sku="OVR", size="XL", price_override="249.00")
        ProductVariant.objects.create(product=product, sku="BASE", size="S")
        response = anon_client.get(reverse("product-detail", kwargs={"slug": product.slug}))
        prices = {v["sku"]: v["effective_price"] for v in response.data["variants"]}
        assert prices["OVR"] == "249.00"
        assert prices["BASE"] == str(product.base_price)


class TestSearchFilterSort:
    def _create(self, category, **kwargs):
        from apps.catalog.models import Product

        defaults = dict(category=category, base_price="100.00", is_published=True)
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    def test_search_by_title(self, anon_client, category):
        self._create(category, title="Leather Jacket", slug="leather-jacket")
        self._create(category, title="Denim Jeans", slug="denim-jeans")
        response = anon_client.get(reverse("product-list"), {"search": "Leather"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["leather-jacket"]

    def test_filter_by_category_slug_includes_descendants(self, anon_client, category, child_category):
        self._create(category, title="Parent Item", slug="parent-item")
        self._create(child_category, title="Child Item", slug="child-item")
        response = anon_client.get(reverse("product-list"), {"category": "outerwear"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert set(slugs) == {"parent-item", "child-item"}

    def test_filter_by_size(self, anon_client, category):
        from apps.catalog.models import ProductVariant

        p = self._create(category, title="Sized", slug="sized")
        ProductVariant.objects.create(product=p, sku="SIZED-M", size="M")
        self._create(category, title="Other", slug="other-item")
        response = anon_client.get(reverse("product-list"), {"size": "M"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["sized"]

    def test_filter_by_price_range(self, anon_client, category):
        self._create(category, title="Cheap", slug="cheap", base_price="50.00")
        self._create(category, title="Pricey", slug="pricey", base_price="500.00")
        response = anon_client.get(reverse("product-list"), {"price_min": "100", "price_max": "1000"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["pricey"]

    def test_sort_by_price_ascending(self, anon_client, category):
        self._create(category, title="Expensive", slug="expensive", base_price="300.00")
        self._create(category, title="Cheap", slug="cheap", base_price="30.00")
        response = anon_client.get(reverse("product-list"), {"ordering": "base_price"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["cheap", "expensive"]

    def test_invalid_category_returns_empty(self, anon_client, product):
        response = anon_client.get(reverse("product-list"), {"category": "does-not-exist"})
        assert response.data["results"] == []
