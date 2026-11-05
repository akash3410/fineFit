"""Tests for the staff dashboard's catalog and order workflows."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import MovementReason, StockMovement, StockRecord
from apps.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusChange,
    ReturnRequest,
    ReturnRequestStatus,
)
from apps.orders.services import OrderService

User = get_user_model()


class ProductInventorySyncTests(TestCase):
    """Saving a variant's stock in the dashboard must reach the inventory ledger.

    The storefront cart validates availability against ``StockRecord`` only, so a
    variant with a declared stock but no record looks purchasable on the product
    page and is then refused with "currently unavailable".
    """

    def setUp(self):
        self.category = Category.objects.create(name="Apparel", slug="apparel")
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="ValidPassword123!",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def _product_form_payload(self, **overrides):
        payload = {
            "title": "Formal Blazer",
            "category": str(self.category.pk),
            "description": "Tailored blazer.",
            "price": "250.00",
            "stock": "7",
            "status": "active",
            "is_published": "on",
            "variant_sku": ["FORMAL-M"],
            "variant_size": ["M"],
            "variant_color": ["Red"],
            "variant_stock": ["7"],
            "variant_price": ["250.00"],
        }
        payload.update(overrides)
        return payload

    def test_adding_a_product_creates_a_stock_record_for_each_variant(self):
        response = self.client.post(
            reverse("admin_panel:product_add"), self._product_form_payload()
        )

        self.assertEqual(response.status_code, 302)
        variant = ProductVariant.objects.get(sku="FORMAL-M")
        record = StockRecord.objects.get(variant=variant)
        self.assertEqual(record.quantity_on_hand, 7)
        self.assertEqual(record.available_quantity, 7)

        movement = StockMovement.objects.get(stock_record=record)
        self.assertEqual(movement.reason, MovementReason.INITIAL_STOCK)
        self.assertEqual(movement.quantity_delta, 7)

    def test_editing_variant_stock_corrects_the_existing_record(self):
        product = Product.objects.create(
            title="Formal Blazer",
            slug="formal-blazer",
            category=self.category,
            price="250.00",
            is_published=True,
        )
        variant = ProductVariant.objects.create(
            product=product, sku="FORMAL-M", size="M", color_name="Red", stock=7
        )
        StockRecord.objects.create(
            variant=variant, quantity_on_hand=7, quantity_reserved=0, low_stock_threshold=5
        )

        response = self.client.post(
            reverse("admin_panel:product_edit", kwargs={"pk": product.pk}),
            self._product_form_payload(
                variant_id=[str(variant.pk)],
                variant_stock=["3"],
                stock="3",
            ),
        )

        self.assertEqual(response.status_code, 302)
        variant.refresh_from_db()
        record = StockRecord.objects.get(variant=variant)
        self.assertEqual(variant.stock, 3)
        self.assertEqual(record.quantity_on_hand, 3)

        movement = StockMovement.objects.latest("created_at")
        self.assertEqual(movement.reason, MovementReason.CORRECTION)
        self.assertEqual(movement.quantity_delta, -4)


class OrderDashboardTests(TestCase):
    """Storefront orders must be visible and actionable in the custom admin panel."""

    def setUp(self):
        self.category = Category.objects.create(name="Apparel", slug="apparel")
        self.product = Product.objects.create(
            title="Formal Blazer",
            slug="formal-blazer",
            category=self.category,
            price="250.00",
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="FORMAL-M",
            size="M",
            color_name="Red",
            stock=5,
        )
        self.record = StockRecord.objects.create(
            variant=self.variant,
            quantity_on_hand=5,
            quantity_reserved=0,
            low_stock_threshold=2,
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="ValidPassword123!",
            is_staff=True,
        )
        self.order = self._create_order()

    def _create_order(self, quantity: int = 2) -> Order:
        order = Order.objects.create(
            session_key="guest-session-key",
            customer_name="Nadia Rahman",
            customer_phone="+8801712345678",
            customer_email="nadia@example.com",
            shipping_address={
                "address_line1": "House 12, Road 5",
                "address_line2": "Dhanmondi",
                "city": "Dhaka",
                "area": "Dhanmondi",
                "postal_code": "1205",
                "country": "Bangladesh",
            },
            notes="Call before delivery.",
            subtotal=Decimal("250.00") * quantity,
            shipping_fee=Decimal("0.00"),
            total=Decimal("250.00") * quantity,
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_title=self.product.title,
            variant_sku=self.variant.sku,
            size=self.variant.size,
            color_name=self.variant.color_name,
            unit_price=Decimal("250.00"),
            quantity=quantity,
            line_total=Decimal("250.00") * quantity,
        )
        return order

    def test_order_list_shows_orders_placed_on_the_storefront(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin_panel:order_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
        self.assertContains(response, "Nadia Rahman")
        self.assertContains(response, "Pending")

    def test_order_list_filters_by_status(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel:order_list"), {"status": OrderStatus.CONFIRMED}
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.order.order_number)

    def test_order_pages_are_staff_only(self):
        customer = User.objects.create_user(
            email="customer@example.com", password="ValidPassword123!"
        )
        self.client.force_login(customer)

        list_response = self.client.get(reverse("admin_panel:order_list"))
        detail_response = self.client.get(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            )
        )

        self.assertEqual(list_response.status_code, 302)
        self.assertEqual(detail_response.status_code, 302)

    def test_order_detail_shows_customer_delivery_and_items(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nadia Rahman")
        self.assertContains(response, "+8801712345678")
        self.assertContains(response, "Dhanmondi")
        self.assertContains(response, "House 12, Road 5")
        self.assertContains(response, "FORMAL-M")
        self.assertContains(response, "Call before delivery.")
        self.assertContains(response, "500.00")

    def test_order_detail_returns_404_for_unknown_number(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel:order_view", kwargs={"order_number": "ORD-2026-ZZZZZZ"})
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_can_confirm_an_order(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"status": OrderStatus.CONFIRMED},
        )

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.record.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 5)

    def test_cancelling_an_order_returns_units_to_stock(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"status": OrderStatus.CANCELLED},
        )

        self.order.refresh_from_db()
        self.record.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(self.record.quantity_on_hand, 7)
        self.assertEqual(self.variant.stock, 7)

        movement = StockMovement.objects.latest("created_at")
        self.assertEqual(movement.reason, MovementReason.ORDER_CANCELLED)
        self.assertEqual(movement.quantity_delta, 2)
        self.assertEqual(movement.reference_id, str(self.order.id))

    def test_terminal_order_cannot_be_reopened(self):
        self.client.force_login(self.staff)
        self.order.status = OrderStatus.CANCELLED
        self.order.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"status": OrderStatus.CONFIRMED},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot change status")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)

    def _post_return(self, quantities: dict[int, int], note: str = "") -> None:
        payload = {"action": "return", "note": note}
        for item_id, quantity in quantities.items():
            payload[f"return_qty_{item_id}"] = str(quantity)
        return self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            payload,
        )

    def _confirm_order(self) -> None:
        self.order.status = OrderStatus.CONFIRMED
        self.order.save(update_fields=["status", "updated_at"])

    def test_status_change_records_who_changed_it(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"action": "status", "status": OrderStatus.PROCESSING, "note": "Packed"},
        )

        change = OrderStatusChange.objects.get(order=self.order)
        self.assertEqual(change.previous_status, OrderStatus.PENDING)
        self.assertEqual(change.new_status, OrderStatus.PROCESSING)
        self.assertEqual(change.changed_by, self.staff)
        self.assertEqual(change.note, "Packed")

    def test_order_detail_shows_status_history(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"action": "status", "status": OrderStatus.CONFIRMED, "note": "Verified by phone"},
        )

        response = self.client.get(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            )
        )

        self.assertContains(response, "Verified by phone")
        self.assertContains(response, self.staff.email)

    def test_partial_return_restocks_only_the_returned_units(self):
        self._confirm_order()
        self.client.force_login(self.staff)
        item = self.order.items.first()

        self._post_return({item.pk: 1}, note="Wrong size")

        item.refresh_from_db()
        self.order.refresh_from_db()
        self.record.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(item.returned_quantity, 1)
        self.assertEqual(item.remaining_quantity, 1)
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.assertEqual(self.record.quantity_on_hand, 6)
        self.assertEqual(self.variant.stock, 6)

        movement = StockMovement.objects.latest("created_at")
        self.assertEqual(movement.reason, MovementReason.RETURN)
        self.assertEqual(movement.quantity_delta, 1)

        change = OrderStatusChange.objects.latest("created_at")
        self.assertEqual(change.changed_by, self.staff)
        self.assertEqual(change.note, "Wrong size")
        self.assertEqual(change.previous_status, change.new_status)

    def test_oversized_return_is_rejected_without_touching_stock(self):
        self._confirm_order()
        self.client.force_login(self.staff)
        item = self.order.items.first()

        response = self._post_return({item.pk: 3}, note="Too many")

        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(item.returned_quantity, 0)
        self.assertEqual(self.record.quantity_on_hand, 5)
        self.assertFalse(
            StockMovement.objects.filter(reason=MovementReason.RETURN).exists()
        )

    def test_returning_every_unit_marks_the_order_returned(self):
        self._confirm_order()
        self.client.force_login(self.staff)
        item = self.order.items.first()

        self._post_return({item.pk: 2}, note="Both damaged")

        self.order.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.RETURNED)
        self.assertEqual(self.record.quantity_on_hand, 7)

        # A terminal, fully returned order cannot be returned again.
        self._post_return({item.pk: 1})
        item.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(item.returned_quantity, 2)
        self.assertEqual(self.record.quantity_on_hand, 7)

    def test_returns_require_a_confirmed_order(self):
        self.client.force_login(self.staff)
        item = self.order.items.first()

        self._post_return({item.pk: 1})

        item.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(item.returned_quantity, 0)
        self.assertEqual(self.record.quantity_on_hand, 5)

    def test_cancelling_after_a_partial_return_does_not_restock_twice(self):
        self._confirm_order()
        self.client.force_login(self.staff)
        item = self.order.items.first()
        self._post_return({item.pk: 1})

        self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"action": "status", "status": OrderStatus.CANCELLED, "note": "Out of stock"},
        )

        self.order.refresh_from_db()
        item.refresh_from_db()
        self.record.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(item.returned_quantity, 2)
        # 5 on-hand (already sold) + 1 returned + 1 cancelled = 7, the
        # pre-sale balance. Restocking all 2 units again would give 8.
        self.assertEqual(self.record.quantity_on_hand, 7)
        restocked = sum(
            movement.quantity_delta
            for movement in StockMovement.objects.filter(
                reason__in=[MovementReason.RETURN, MovementReason.ORDER_CANCELLED]
            )
        )
        self.assertEqual(restocked, 2)

    def test_django_admin_status_is_read_only(self):
        """Status must only change through the audited OrderService path."""
        from apps.orders.admin import OrderAdmin

        self.assertIn("status", OrderAdmin.readonly_fields)

        superuser = User.objects.create_user(
            email="root@example.com",
            password="ValidPassword123!",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(superuser)

        response = self.client.get(f"/admin/orders/order/{self.order.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
        self.assertContains(
            response,
            f"/admin/orders/{self.order.order_number}/",
        )

    def _delivered_order_with_request(self, quantity: int = 1) -> ReturnRequest:
        """Simulate a customer asking to return units after delivery."""
        self.order.status = OrderStatus.DELIVERED
        self.order.save(update_fields=["status", "updated_at"])
        return OrderService.request_return(
            self.order.pk,
            {self.order.items.first().pk: quantity},
            reason="Does not fit",
        )

    def _review_return_request(self, return_request, action, note=""):
        return self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {
                "action": action,
                "return_request_id": str(return_request.pk),
                "note": note,
            },
            follow=True,
        )

    def test_approving_a_customer_return_request_restocks_the_units(self):
        return_request = self._delivered_order_with_request(quantity=1)
        self.client.force_login(self.staff)

        response = self._review_return_request(
            return_request, "approve_return", note="Inspected, resellable"
        )

        self.assertContains(response, "Return request approved")
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, ReturnRequestStatus.APPROVED)
        self.assertEqual(return_request.resolved_by, self.staff)
        self.assertEqual(return_request.staff_note, "Inspected, resellable")

        item = self.order.items.first()
        item.refresh_from_db()
        self.record.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(item.returned_quantity, 1)
        self.assertEqual(self.record.quantity_on_hand, 6)
        self.assertEqual(self.variant.stock, 6)

        movement = StockMovement.objects.latest("created_at")
        self.assertEqual(movement.reason, MovementReason.RETURN)
        self.assertEqual(movement.quantity_delta, 1)

        change = OrderStatusChange.objects.latest("created_at")
        self.assertEqual(change.changed_by, self.staff)
        self.assertEqual(change.note, "Inspected, resellable")

    def test_declining_a_customer_return_request_leaves_stock_alone(self):
        return_request = self._delivered_order_with_request(quantity=1)
        self.client.force_login(self.staff)

        response = self._review_return_request(
            return_request, "decline_return", note="Outside the return window"
        )

        self.assertContains(response, "Return request declined")
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, ReturnRequestStatus.DECLINED)
        self.assertEqual(return_request.staff_note, "Outside the return window")
        self.record.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 5)
        self.assertFalse(
            StockMovement.objects.filter(reason=MovementReason.RETURN).exists()
        )

    def test_a_return_request_can_only_be_reviewed_once(self):
        return_request = self._delivered_order_with_request(quantity=1)
        self.client.force_login(self.staff)
        self._review_return_request(return_request, "approve_return")

        response = self._review_return_request(return_request, "approve_return")

        self.assertContains(response, "already been reviewed")
        self.record.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 6)

    def test_order_detail_lists_customer_return_requests(self):
        self._delivered_order_with_request(quantity=2)
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            )
        )

        self.assertContains(response, "Customer Return Requests")
        self.assertContains(response, "Does not fit")
        self.assertContains(response, "Approve &amp; restock")
        self.assertContains(response, "awaiting review")

    def test_unknown_status_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                "admin_panel:order_view",
                kwargs={"order_number": self.order.order_number},
            ),
            {"status": "NOT_A_STATUS"},
            follow=True,
        )

        self.assertContains(response, "Unknown order status.")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
