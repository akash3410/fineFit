"""
Tests for Inventory API endpoints, permissions, and public availability.
"""

import uuid
import pytest
from django.urls import reverse

from apps.inventory.models import MovementReason, StockMovement, StockRecord


@pytest.mark.django_db
class TestStockRecordApiPermissions:
    def test_anonymous_cannot_access_records(self, anon_client):
        response = anon_client.get(reverse("stock-record-list"))
        assert response.status_code in (401, 403)

    def test_customer_cannot_access_records(self, user_client):
        response = user_client.get(reverse("stock-record-list"))
        assert response.status_code == 403

    def test_staff_without_permissions_cannot_access_records(self, staff_no_perms_client):
        response = staff_no_perms_client.get(reverse("stock-record-list"))
        assert response.status_code == 403

    def test_viewer_can_list_and_retrieve_records(self, viewer_client, stock_record):
        # List
        response = viewer_client.get(reverse("stock-record-list"))
        assert response.status_code == 200
        records = response.data if isinstance(response.data, list) else response.data["results"]
        assert len(records) == 1
        assert records[0]["variant_sku"] == stock_record.variant.sku

        # Retrieve
        url = reverse("stock-record-detail", kwargs={"variant_id": stock_record.variant.id})
        detail_res = viewer_client.get(url)
        assert detail_res.status_code == 200
        assert detail_res.data["quantity_on_hand"] == stock_record.quantity_on_hand

    def test_viewer_cannot_adjust_stock(self, viewer_client, stock_record):
        url = reverse("stock-record-adjust", kwargs={"variant_id": stock_record.variant.id})
        response = viewer_client.post(
            url,
            {"action": "INCREASE", "quantity": 10},
            format="json",
        )
        assert response.status_code == 403

    def test_manager_can_adjust_stock(self, manager_client, stock_record):
        url = reverse("stock-record-adjust", kwargs={"variant_id": stock_record.variant.id})
        response = manager_client.post(
            url,
            {
                "action": "INCREASE",
                "quantity": 10,
                "reason": "PURCHASE_RECEIPT",
                "notes": "Added via API",
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["quantity_on_hand"] == 30
        assert response.data["available_quantity"] == 25


@pytest.mark.django_db
class TestStockRecordApiOperations:
    def test_create_stock_record_endpoint(self, manager_client, variant_two):
        url = reverse("stock-record-list")
        payload = {
            "variant_id": str(variant_two.id),
            "quantity_on_hand": 25,
            "quantity_reserved": 0,
            "low_stock_threshold": 5,
            "notes": "Created via API",
        }
        response = manager_client.post(url, payload, format="json")
        assert response.status_code == 201
        assert response.data["quantity_on_hand"] == 25
        assert response.data["variant_sku"] == variant_two.sku

    def test_adjust_decrease_insufficient_stock_returns_400(self, manager_client, stock_record):
        url = reverse("stock-record-adjust", kwargs={"variant_id": stock_record.variant.id})
        # Initial available: 15. Attempting to decrease 50
        response = manager_client.post(
            url,
            {"action": "DECREASE", "quantity": 50},
            format="json",
        )
        assert response.status_code == 400
        assert "Insufficient available stock" in response.data["detail"]

    def test_adjust_reserve_and_release_flow(self, manager_client, stock_record):
        url = reverse("stock-record-adjust", kwargs={"variant_id": stock_record.variant.id})

        # Reserve 5 units (reserved becomes 10)
        res_reserve = manager_client.post(
            url,
            {"action": "RESERVE", "quantity": 5},
            format="json",
        )
        assert res_reserve.status_code == 200
        assert res_reserve.data["quantity_reserved"] == 10
        assert res_reserve.data["available_quantity"] == 10

        # Release 4 units (reserved becomes 6)
        res_release = manager_client.post(
            url,
            {"action": "RELEASE", "quantity": 4},
            format="json",
        )
        assert res_release.status_code == 200
        assert res_release.data["quantity_reserved"] == 6
        assert res_release.data["available_quantity"] == 14

    def test_stock_record_filtering(self, manager_client, product):
        from apps.catalog.models import ProductVariant

        v1 = ProductVariant.objects.create(product=product, sku="F-1", size="S")
        v2 = ProductVariant.objects.create(product=product, sku="F-2", size="M")

        StockRecord.objects.create(variant=v1, quantity_on_hand=20, quantity_reserved=0, low_stock_threshold=5)
        StockRecord.objects.create(variant=v2, quantity_on_hand=3, quantity_reserved=0, low_stock_threshold=5)

        # Filter low stock
        url = reverse("stock-record-list") + "?low_stock=true"
        response = manager_client.get(url)
        assert response.status_code == 200
        results = response.data if isinstance(response.data, list) else response.data["results"]
        skus = [r["variant_sku"] for r in results]
        assert "F-2" in skus
        assert "F-1" not in skus


@pytest.mark.django_db
class TestStockMovementApi:
    def test_movement_requires_view_permission(self, staff_no_perms_client, stock_record):
        response = staff_no_perms_client.get(reverse("stock-movement-list"))
        assert response.status_code == 403

    def test_viewer_can_read_movement_logs(self, viewer_client, stock_record, regular_user):
        StockMovement.objects.create(
            stock_record=stock_record,
            variant=stock_record.variant,
            quantity_delta=10,
            reason=MovementReason.PURCHASE_RECEIPT,
            actor=regular_user,
            reference_id="PO-AUDIT-1",
        )
        response = viewer_client.get(reverse("stock-movement-list"))
        assert response.status_code == 200
        results = response.data if isinstance(response.data, list) else response.data["results"]
        assert len(results) == 1
        assert results[0]["reference_id"] == "PO-AUDIT-1"

    def test_movement_cannot_be_created_via_api(self, manager_client, stock_record):
        # StockMovement has no create endpoint; should return 403 or 405
        response = manager_client.post(
            reverse("stock-movement-list"),
            {"quantity_delta": 5},
            format="json",
        )
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestPublicAvailabilityApi:
    def test_public_availability_with_stock_record(self, anon_client, stock_record):
        url = reverse("variant-availability", kwargs={"variant_id": stock_record.variant.id})
        response = anon_client.get(url)
        assert response.status_code == 200
        assert response.data["is_in_stock"] is True
        assert response.data["is_low_stock"] is False
        assert response.data["status"] == "IN_STOCK"
        assert response.data["sku"] == stock_record.variant.sku
        # Ensure exact quantities are NOT leaked in public response
        assert "quantity_on_hand" not in response.data
        assert "available_quantity" not in response.data

    def test_public_availability_without_stock_record_strictly_out_of_stock(
        self, anon_client, variant_two
    ):
        url = reverse("variant-availability", kwargs={"variant_id": variant_two.id})
        response = anon_client.get(url)
        assert response.status_code == 200
        assert response.data["is_in_stock"] is False
        assert response.data["is_low_stock"] is False
        assert response.data["status"] == "OUT_OF_STOCK"

    def test_public_availability_inactive_or_missing_variant_returns_404(
        self, anon_client, variant
    ):
        variant.is_active = False
        variant.save()
        url = reverse("variant-availability", kwargs={"variant_id": variant.id})
        response = anon_client.get(url)
        assert response.status_code == 404

    def test_catalog_product_detail_includes_stock_status(
        self, anon_client, product, stock_record
    ):
        # Verify catalog endpoint includes derived availability without errors
        url = reverse("product-detail", kwargs={"slug": product.slug})
        response = anon_client.get(url)
        assert response.status_code == 200
        variant_data = response.data["variants"][0]
        assert variant_data["sku"] == stock_record.variant.sku
        assert variant_data["is_in_stock"] is True
        assert variant_data["stock_status"] == "IN_STOCK"
