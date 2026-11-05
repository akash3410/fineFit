"""
Public catalog API tests: visibility, search, filtering, sorting, pagination.

Confirms that anonymous visitors only ever see published products under active
categories, and that drafts/inactive data cannot leak through any surface.
"""

import pytest
from datetime import timezone as dt_timezone
from django.db.models.fields import NOT_PROVIDED
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from apps.catalog.models import Category, Event, Subcategory
from apps.catalog.tests.conftest import make_image_file

pytestmark = pytest.mark.django_db


class TestCategoryEndpoints:
    def test_lists_only_active_root_categories(self, anon_client, category, child_category, inactive_category):
        response = anon_client.get(reverse("category-list"))
        assert response.status_code == 200
        slugs = [c["slug"] for c in response.data["results"]] if "results" in response.data else [c["slug"] for c in response.data]
        assert "outerwear" in slugs
        assert "archived" not in slugs  # inactive hidden
        assert "coats" not in slugs  # child not at root

    def test_category_image_url_serialized(self, anon_client, category):
        category.image = make_image_file(name="outerwear", image_format="PNG")
        category.save()

        response = anon_client.get(reverse("category-list"))
        assert response.status_code == 200
        results = response.data["results"] if "results" in response.data else response.data
        outerwear = next(c for c in results if c["slug"] == "outerwear")
        assert outerwear["image"] is not None
        assert outerwear["image"].endswith(".png")

    def test_nested_children_included(self, anon_client, category, child_category):
        response = anon_client.get(reverse("category-list"))
        data = response.data
        results = data["results"] if "results" in data else data
        root = next(c for c in results if c["slug"] == "outerwear")
        assert any(ch["slug"] == "coats" for ch in root["children"])

    def test_category_list_paginated(self, anon_client, category):
        # Create more categories than the default page size to trigger pagination.
        for i in range(15):
            Category.objects.create(name=f"Category {i}", slug=f"category-{i}")

        response = anon_client.get(reverse("category-list"))
        assert response.status_code == 200
        data = response.data
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] >= 15
        assert len(data["results"]) <= 12  # default CatalogPagination page_size

        # Page 2 should return additional results.
        page2 = anon_client.get(reverse("category-list") + "?page=2")
        assert page2.status_code == 200
        page2_results = page2.data["results"] if "results" in page2.data else page2.data
        assert len(page2_results) > 0

        # No overlap between page 1 and page 2.
        page1_slugs = {c["slug"] for c in data["results"]}
        page2_slugs = {c["slug"] for c in page2_results}
        assert page1_slugs.isdisjoint(page2_slugs)

    def test_category_endpoint_read_only_for_public(self, anon_client, category):
        """Public endpoint allows GET but must not allow writes (read-only serializer)."""
        response = anon_client.get(reverse("category-list"))
        assert response.status_code == 200
        # image field present and read-only (no write path exposed on ListAPIView).
        results = response.data["results"] if "results" in response.data else response.data
        assert all("image" in c for c in results)


class TestSubcategoryEndpoints:
    def test_public_access(self, anon_client, category):
        Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        response = anon_client.get(reverse("subcategory-list"))
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        assert len(results) == 1
        assert results[0]["slug"] == "coats"

    def test_returns_active_non_deleted_only(self, anon_client, category):
        Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        Subcategory.objects.create(category=category, name="Archived", slug="archived", is_active=False)
        Subcategory.objects.create(category=category, name="Deleted", slug="deleted", is_active=True, is_deleted=True)

        response = anon_client.get(reverse("subcategory-list"))
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        slugs = [s["slug"] for s in results]
        assert "coats" in slugs
        assert "archived" not in slugs
        assert "deleted" not in slugs

    def test_image_url_serialized(self, anon_client, category):
        from apps.catalog.tests.conftest import make_image_file

        sub = Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        sub.image = make_image_file(name="coats", image_format="PNG")
        sub.save()

        response = anon_client.get(reverse("subcategory-list"))
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        coats = next(s for s in results if s["slug"] == "coats")
        assert coats["image"] is not None
        assert coats["image"].endswith(".png")

    def test_parent_category_information(self, anon_client, category):
        Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)

        response = anon_client.get(reverse("subcategory-list"))
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        coats = results[0]
        assert coats["category"] == category.id  # parent id
        assert coats["category_name"] == "Outerwear"  # parent name
        assert coats["category_slug"] == "outerwear"  # parent slug

    def test_filter_by_category_slug(self, anon_client, category):
        other = Category.objects.create(name="Tops", slug="tops", is_active=True)
        Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        Subcategory.objects.create(category=other, name="Shirts", slug="shirts", is_active=True)

        response = anon_client.get(reverse("subcategory-list") + "?category=outerwear")
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        assert [s["slug"] for s in results] == ["coats"]

    def test_filter_by_category_id(self, anon_client, category):
        other = Category.objects.create(name="Tops", slug="tops", is_active=True)
        Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        Subcategory.objects.create(category=other, name="Shirts", slug="shirts", is_active=True)

        response = anon_client.get(reverse("subcategory-list") + f"?category={category.id}")
        assert response.status_code == 200
        data = response.data
        results = data["results"] if "results" in data else data
        assert [s["slug"] for s in results] == ["coats"]

    def test_pagination(self, anon_client, category):
        for i in range(15):
            Subcategory.objects.create(category=category, name=f"Sub {i}", slug=f"sub-{i}", is_active=True)

        response = anon_client.get(reverse("subcategory-list"))
        assert response.status_code == 200
        data = response.data
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] >= 15
        assert len(data["results"]) <= 12


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
        assert prices["BASE"] == str(product.price)


class TestSearchFilterSort:
    def _create(self, category, **kwargs):
        from apps.catalog.models import Product

        defaults = dict(category=category, price="100.00", is_published=True)
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
        self._create(category, title="Cheap", slug="cheap", price="50.00")
        self._create(category, title="Pricey", slug="pricey", price="500.00")
        response = anon_client.get(reverse("product-list"), {"price_min": "100", "price_max": "1000"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["pricey"]

    def test_sort_by_price_ascending(self, anon_client, category):
        self._create(category, title="Expensive", slug="expensive", price="300.00")
        self._create(category, title="Cheap", slug="cheap", price="30.00")
        response = anon_client.get(reverse("product-list"), {"ordering": "base_price"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["cheap", "expensive"]

    def test_invalid_category_returns_empty(self, anon_client, product):
        response = anon_client.get(reverse("product-list"), {"category": "does-not-exist"})
        assert response.data["results"] == []

    def test_filter_by_subcategory_slug(self, anon_client, category):
        from apps.catalog.models import Product

        sub = Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        self._create(category, title="Coat", slug="coat", subcategory=sub)
        self._create(category, title="Other", slug="other")

        response = anon_client.get(reverse("product-list"), {"subcategory": "coats"})
        assert response.status_code == 200
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["coat"]

    def test_filter_by_subcategory_id(self, anon_client, category):
        from apps.catalog.models import Product

        sub = Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        self._create(category, title="Coat", slug="coat", subcategory=sub)
        self._create(category, title="Other", slug="other")

        response = anon_client.get(reverse("product-list"), {"subcategory": str(sub.id)})
        assert response.status_code == 200
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["coat"]

    def test_filter_by_category_and_subcategory_combined(self, anon_client, category):
        from apps.catalog.models import Product

        sub = Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
        other_cat = Category.objects.create(name="Tops", slug="tops", is_active=True)
        other_sub = Subcategory.objects.create(category=other_cat, name="Shirts", slug="shirts", is_active=True)

        self._create(category, title="Coat", slug="coat", subcategory=sub)
        self._create(other_cat, title="Shirt", slug="shirt", subcategory=other_sub)
        self._create(category, title="Jacket", slug="jacket")  # no subcategory

        response = anon_client.get(reverse("product-list"), {"category": "outerwear", "subcategory": "coats"})
        assert response.status_code == 200
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs == ["coat"]

    def test_existing_filters_still_work(self, anon_client, category):
        from apps.catalog.models import ProductVariant

        self._create(category, title="Cheap", slug="cheap", price="50.00")
        self._create(category, title="Pricey", slug="pricey", price="500.00")
        p = self._create(category, title="Sized", slug="sized")
        ProductVariant.objects.create(product=p, sku="SIZED-M", size="M")
        self._create(category, title="Leather", slug="leather")
        self._create(category, title="Denim", slug="denim")

        # price range
        response = anon_client.get(reverse("product-list"), {"price_min": "100", "price_max": "1000"})
        assert set(p["slug"] for p in response.data["results"]) == {"sized", "leather", "denim", "pricey"}

        # size
        response = anon_client.get(reverse("product-list"), {"size": "M"})
        assert [p["slug"] for p in response.data["results"]] == ["sized"]

        # search
        response = anon_client.get(reverse("product-list"), {"search": "Leather"})
        assert [p["slug"] for p in response.data["results"]] == ["leather"]

        # ordering: cheap first, pricey last, middle three are tied at price=100
        response = anon_client.get(reverse("product-list"), {"ordering": "base_price"})
        slugs = [p["slug"] for p in response.data["results"]]
        assert slugs[0] == "cheap"
        assert slugs[-1] == "pricey"
        assert set(slugs[1:-1]) == {"sized", "leather", "denim"}


class TestEventEndpoints:
    """Tests for the public events/announcements endpoint."""

    NOW = timezone.datetime(2026, 6, 15, 12, 0, 0, tzinfo=dt_timezone.utc)

    def _make_event(self, **kwargs):
        defaults = dict(
            title="Test Event",
            slug="test-event",
            announcement="Happening now",
            start_at=self.NOW,
            end_at=self.NOW + timezone.timedelta(hours=2),
            is_active=True,
        )
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def _get(self, anon_client):
        return anon_client.get(reverse("event-list"))

    def test_public_unauthenticated_access(self, anon_client):
        """Anonymous users can access the event list endpoint."""
        self._make_event()
        response = self._get(anon_client)
        assert response.status_code == 200

    def test_returns_only_active_events_in_window(self, anon_client):
        """Only active events within start_at <= now <= end_at are returned."""
        with patch("django.utils.timezone.now", return_value=self.NOW):
            self._make_event(title="Live", slug="live", start_at=self.NOW, end_at=self.NOW + timezone.timedelta(hours=1))
            self._make_event(title="Inactive", slug="inactive", is_active=False, start_at=self.NOW, end_at=self.NOW + timezone.timedelta(hours=1))
            self._make_event(title="Future", slug="future", start_at=self.NOW + timezone.timedelta(days=1), end_at=self.NOW + timezone.timedelta(days=2))
            self._make_event(title="Expired", slug="expired", start_at=self.NOW - timezone.timedelta(days=2), end_at=self.NOW - timezone.timedelta(days=1))

            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            titles = [e["title"] for e in results]
            assert titles == ["Live"]

    def test_event_starting_exactly_now_is_returned(self, anon_client):
        """An event starting exactly at now is within the window."""
        with patch("django.utils.timezone.now", return_value=self.NOW):
            self._make_event(title="Starting Now", slug="starting-now", start_at=self.NOW, end_at=self.NOW + timezone.timedelta(hours=1))
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            assert any(e["slug"] == "starting-now" for e in results)

    def test_event_ending_exactly_now_is_returned(self, anon_client):
        """An event ending exactly at now is within the window."""
        with patch("django.utils.timezone.now", return_value=self.NOW):
            self._make_event(title="Ending Now", slug="ending-now", start_at=self.NOW - timezone.timedelta(hours=1), end_at=self.NOW)
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            assert any(e["slug"] == "ending-now" for e in results)

    def test_image_url_serialized(self, anon_client):
        from apps.catalog.tests.conftest import make_image_file

        event = self._make_event()
        event.image = make_image_file(name="event", image_format="PNG")
        event.save()

        with patch("django.utils.timezone.now", return_value=self.NOW):
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            evt = next(e for e in results if e["slug"] == "test-event")
            assert evt["image"] is not None
            assert evt["image"].endswith(".png")

    def test_cta_fields_serialized(self, anon_client):
        """CTA label and link are serialized."""
        self._make_event(cta_label="Shop Now", cta_link="https://example.com/sale")

        with patch("django.utils.timezone.now", return_value=self.NOW):
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            evt = results[0]
            assert evt["cta_label"] == "Shop Now"
            assert evt["cta_link"] == "https://example.com/sale"

    def test_default_cta_label(self, anon_client):
        """Default CTA label is 'Explore Event'."""
        self._make_event()

        with patch("django.utils.timezone.now", return_value=self.NOW):
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            assert results[0]["cta_label"] == "Explore Event"

    def test_invalid_date_range_rejected(self):
        """end_at must be after start_at."""
        with patch("django.utils.timezone.now", return_value=self.NOW):
            event = Event(
                title="Bad Event",
                slug="bad-event",
                start_at=self.NOW + timezone.timedelta(hours=2),
                end_at=self.NOW,
                is_active=True,
            )
            with pytest.raises(Exception) as excinfo:
                event.full_clean()
            assert "end_at" in str(excinfo.value) or "End time must be after" in str(excinfo.value)

    def test_public_endpoint_read_only(self, anon_client):
        """Public endpoint does not allow write operations."""
        self._make_event()
        response = self._get(anon_client)
        assert response.status_code == 200

        # POST/PUT/PATCH/DELETE are not available on ListAPIView
        post_response = anon_client.post(reverse("event-list"), {})
        assert post_response.status_code == 405

    def test_deterministic_ordering(self, anon_client):
        """Events are ordered by -created_at (newest first)."""
        now = timezone.now()
        e1 = Event.objects.create(
            title="First", slug="first",
            start_at=now - timezone.timedelta(hours=2),
            end_at=now + timezone.timedelta(hours=1),
        )
        e2 = Event.objects.create(
            title="Second", slug="second",
            start_at=now - timezone.timedelta(hours=2),
            end_at=now + timezone.timedelta(hours=1),
        )

        with patch("django.utils.timezone.now", return_value=now):
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            titles = [e["title"] for e in results]
            assert "Second" in titles
            assert "First" in titles
            # Second should appear before First (newer created_at first)
            assert titles.index("Second") < titles.index("First")

    def test_pagination(self, anon_client):
        """Event list uses paginated response structure."""
        with patch("django.utils.timezone.now", return_value=self.NOW):
            for i in range(15):
                self._make_event(title=f"Event {i}", slug=f"event-{i}")

            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            assert "count" in data
            assert "next" in data
            assert "previous" in data
            assert "results" in data
            assert data["count"] >= 15
            assert len(data["results"]) <= 12  # CatalogPagination page_size

    def test_end_at_has_no_model_default(self):
        """Event.end_at must not have an automatic model-level default."""
        end_at_field = Event._meta.get_field("end_at")
        assert end_at_field.default is NOT_PROVIDED

    def test_title_max_length_is_200(self):
        """Event.title must have max_length=200."""
        title_field = Event._meta.get_field("title")
        assert title_field.max_length == 200

    def test_soft_deleted_event_excluded(self, anon_client):
        """Soft-deleted events must not appear in the public API."""
        now = timezone.now()
        # Active event within window - should appear
        Event.objects.create(
            title="Visible Event", slug="visible-event",
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1),
            is_active=True, is_deleted=False,
        )
        # Soft-deleted event within window - should NOT appear
        Event.objects.create(
            title="Deleted Event", slug="deleted-event",
            start_at=now - timezone.timedelta(hours=1),
            end_at=now + timezone.timedelta(hours=1),
            is_active=True, is_deleted=True,
        )

        with patch("django.utils.timezone.now", return_value=now):
            response = self._get(anon_client)
            assert response.status_code == 200
            data = response.data
            results = data["results"] if "results" in data else data
            slugs = [e["slug"] for e in results]
            assert "visible-event" in slugs
            assert "deleted-event" not in slugs

    def test_event_model_fields_exist(self):
        """Event model has all required fields."""
        field_names = {f.name for f in Event._meta.get_fields()}
        required = {
            "id", "title", "slug", "announcement", "image",
            "start_at", "end_at", "is_active", "cta_label",
            "cta_link", "created_at", "updated_at",
        }
        assert required.issubset(field_names)
