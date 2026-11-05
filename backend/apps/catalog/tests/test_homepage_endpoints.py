"""
Homepage-supporting catalog API tests.

Covers the endpoints powering the redesigned homepage: subcategories,
events, and the product list fields/filter used by the storefront.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Event, Product, ProductVariant, Subcategory

pytestmark = pytest.mark.django_db


def test_subcategory_list_returns_active_only(anon_client, category):
    Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
    Subcategory.objects.create(category=category, name="Archived", slug="archived", is_active=False)

    response = anon_client.get(reverse("subcategory-list"))
    assert response.status_code == 200

    data = response.data
    results = data["results"] if "results" in data else data
    slugs = [s["slug"] for s in results]
    assert "coats" in slugs
    assert "archived" not in slugs
    # image field exposed for gallery cards
    coats = next(s for s in results if s["slug"] == "coats")
    assert "image" in coats


def test_subcategory_list_filters_by_parent_category(anon_client, category):
    other = Category.objects.create(name="Tops", slug="tops", is_active=True)
    Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
    Subcategory.objects.create(category=other, name="Shirts", slug="shirts", is_active=True)

    response = anon_client.get(reverse("subcategory-list") + f"?category={category.slug}")
    assert response.status_code == 200
    data = response.data
    results = data["results"] if "results" in data else data
    assert [s["slug"] for s in results] == ["coats"]


def test_event_list_returns_only_active_in_window(anon_client):
    now = timezone.now()
    Event.objects.create(
        title="Live Sale", slug="live-sale", announcement="Happening now",
        start_at=now, end_at=now + timezone.timedelta(hours=1), is_active=True,
    )
    Event.objects.create(
        title="Future", slug="future", announcement="Later",
        start_at=now + timezone.timedelta(days=7), end_at=now + timezone.timedelta(days=8), is_active=True,
    )
    Event.objects.create(
        title="Expired", slug="expired", announcement="Over",
        start_at=now - timezone.timedelta(days=14),
        end_at=now - timezone.timedelta(days=7), is_active=True,
    )
    Event.objects.create(
        title="Inactive", slug="inactive", announcement="Off",
        start_at=now, end_at=now + timezone.timedelta(hours=1), is_active=False,
    )

    response = anon_client.get(reverse("event-list"))
    assert response.status_code == 200
    data = response.data
    results = data["results"] if "results" in data else data
    titles = [e["title"] for e in results]
    assert titles == ["Live Sale"]
    # cta fields present for storefront CTA
    assert results[0]["cta_label"] == "Explore Event"
    assert "cta_link" in results[0]


def test_product_list_exposes_price_fields_and_subcategory_filter(anon_client, category):
    sub = Subcategory.objects.create(category=category, name="Coats", slug="coats", is_active=True)
    coat = Product.objects.create(
        category=category, subcategory=sub, title="Coat", slug="coat",
        price="199.00", discount_price="149.00", stock=5, is_published=True,
    )
    ProductVariant.objects.create(
        product=coat, sku="COAT-M-BLK", size="M", color_name="Black", color_code="#000000",
    )
    other = Product.objects.create(
        category=category, title="Other", slug="other",
        price="99.00", stock=0, is_published=True,
    )
    ProductVariant.objects.create(
        product=other, sku="OTHER-M-BLK", size="M", color_name="Black", color_code="#000000",
    )

    response = anon_client.get(reverse("product-list"))
    assert response.status_code == 200
    data = response.data
    results = data["results"] if "results" in data else data
    coat = next(p for p in results if p["slug"] == "coat")
    assert coat["base_price"] == "199.00"
    assert coat["discount_price"] == "149.00"
    assert coat["stock"] == 5

    response = anon_client.get(reverse("product-list") + "?subcategory=coats")
    assert response.status_code == 200
    data = response.data
    results = data["results"] if "results" in data else data
    assert [p["slug"] for p in results] == ["coat"]
