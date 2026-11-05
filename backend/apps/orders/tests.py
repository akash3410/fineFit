"""Checkout tests: COD order placement, ownership isolation and stock safety."""

import json
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import MovementReason, StockMovement, StockRecord
from apps.orders.models import (
    Order,
    OrderStatus,
    PaymentMethod,
    ReturnRequest,
    ReturnRequestStatus,
)
from apps.orders.services import OrderService

User = get_user_model()


class OrderTestBase(TestCase):
    """Shared catalog + cart helpers for order tests."""

    def setUp(self):
        self.category = Category.objects.create(name="Tees", slug="tees")
        self.product = Product.objects.create(
            title="Relaxed Tee",
            slug="relaxed-tee",
            category=self.category,
            price=Decimal("500.00"),
            is_published=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="TEE-BLK-M",
            size="M",
            color_name="Black",
            stock=10,
        )
        self.record = StockRecord.objects.create(
            variant=self.variant, quantity_on_hand=10, low_stock_threshold=2
        )

    def checkout_payload(self, **overrides):
        payload = {
            "customer_name": "Nadia Rahman",
            "customer_phone": "+8801712345678",
            "customer_email": "nadia@example.com",
            "shipping_address": {
                "address_line1": "House 12, Road 5",
                "address_line2": "Dhanmondi",
                "city": "Dhaka",
                "area": "Dhanmondi",
                "postal_code": "1205",
                "country": "Bangladesh",
            },
            "notes": "Call before delivery.",
            "payment_method": "COD",
        }
        payload.update(overrides)
        return payload

    def post_checkout(self, client: Client, payload: dict | None = None):
        return client.post(
            reverse("orders:order-checkout"),
            data=json.dumps(payload or self.checkout_payload()),
            content_type="application/json",
        )

    def make_guest_cart(self, client: Client | None = None, quantity: int = 2) -> Cart:
        """Create a guest cart owned by a client session (cookie wired up)."""
        client = client or self.client
        session = client.session
        session.create()
        # Persist the session key on the client the way the browser cookie does
        # after the first cart write establishes a guest session.
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        cart = Cart.objects.create(session_key=session.session_key)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=quantity)
        return cart


class GuestCheckoutTests(OrderTestBase):
    def test_guest_places_cod_order_and_cart_is_cleared(self):
        cart = self.make_guest_cart(quantity=2)

        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body["order_number"].startswith("ORD-"))
        self.assertEqual(body["status"], OrderStatus.PENDING)
        self.assertEqual(body["payment_method"], PaymentMethod.COD)
        self.assertEqual(body["subtotal"], "1000.00")
        self.assertEqual(body["shipping_fee"], "0.00")
        self.assertEqual(body["total"], "1000.00")
        self.assertEqual(body["shipping_address"]["city"], "Dhaka")
        self.assertEqual(len(body["items"]), 1)

        order = Order.objects.get()
        self.assertIsNone(order.user_id)
        self.assertEqual(order.session_key, cart.session_key)
        self.assertEqual(order.items.get().variant_sku, "TEE-BLK-M")
        self.assertEqual(order.items.get().product_title, "Relaxed Tee")
        self.assertEqual(order.items.get().unit_price, Decimal("500.00"))

        # Cart is emptied but the cart row itself survives.
        self.assertEqual(cart.items.count(), 0)

    def test_checkout_deducts_stock_and_records_ledger_movement(self):
        self.make_guest_cart(quantity=3)

        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 201, response.content)
        self.record.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 7)
        self.assertEqual(self.variant.stock, 7)

        movement = StockMovement.objects.latest("created_at")
        self.assertEqual(movement.reason, MovementReason.ORDER_CHECKOUT)
        self.assertEqual(movement.quantity_delta, -3)
        self.assertEqual(movement.reference_id, str(Order.objects.get().id))

    def test_guest_can_read_own_order_by_number(self):
        self.make_guest_cart()
        order_number = self.post_checkout(self.client).json()["order_number"]

        response = self.client.get(
            reverse("orders:order-detail", args=[order_number])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_number"], order_number)

    def test_guest_cannot_read_another_sessions_order(self):
        self.make_guest_cart()
        order_number = self.post_checkout(self.client).json()["order_number"]

        other = Client()
        self.make_guest_cart(client=other)
        response = other.get(reverse("orders:order-detail", args=[order_number]))

        self.assertEqual(response.status_code, 404)

    def test_checkout_requires_csrf_token_for_guest_writes(self):
        self.make_guest_cart()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.cookies = self.client.cookies

        response = csrf_client.post(
            reverse("orders:order-checkout"),
            data=json.dumps(self.checkout_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_is_rejected(self):
        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_stock_record_is_rejected(self):
        self.make_guest_cart()
        self.record.delete()

        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_insufficient_stock_is_rejected_without_touching_stock(self):
        self.make_guest_cart(quantity=5)
        self.record.quantity_on_hand = 2
        self.record.save(update_fields=["quantity_on_hand", "updated_at"])

        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Only 2 unit", response.json()["detail"])
        self.assertEqual(Order.objects.count(), 0)
        self.record.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 2)

    def test_unpublished_product_is_rejected(self):
        self.make_guest_cart()
        self.product.is_published = False
        self.product.save(update_fields=["is_published", "updated_at"])

        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_phone_is_rejected(self):
        self.make_guest_cart()

        response = self.post_checkout(
            self.client, self.checkout_payload(customer_phone="not-a-phone")
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("customer_phone", response.json())
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_shipping_address_is_rejected(self):
        self.make_guest_cart()

        response = self.post_checkout(
            self.client, self.checkout_payload(shipping_address={})
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_unsupported_payment_method_is_rejected(self):
        self.make_guest_cart()

        response = self.post_checkout(
            self.client, self.checkout_payload(payment_method="CARD")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


class AuthenticatedCheckoutTests(OrderTestBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="buyer@example.com", password="ValidPassword123!"
        )
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=1)

    def test_authenticated_customer_order_is_attached_to_user(self):
        response = self.post_checkout(self.client)

        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.session_key, "")

    def test_order_history_is_scoped_to_the_customer(self):
        self.post_checkout(self.client)

        other_user = User.objects.create_user(
            email="other@example.com", password="ValidPassword123!"
        )
        other_cart = Cart.objects.create(user=other_user)
        CartItem.objects.create(cart=other_cart, variant=self.variant, quantity=1)
        other_client = Client()
        other_client.force_login(other_user)
        other_client.post(
            reverse("orders:order-checkout"),
            data=json.dumps(self.checkout_payload()),
            content_type="application/json",
        )

        response = self.client.get(reverse("orders:order-list"))

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["customer_email"], "nadia@example.com")

    def test_customer_cannot_read_another_customers_order(self):
        order_number = self.post_checkout(self.client).json()["order_number"]

        intruder = User.objects.create_user(
            email="intruder@example.com", password="ValidPassword123!"
        )
        intruder_client = Client()
        intruder_client.force_login(intruder)

        response = intruder_client.get(
            reverse("orders:order-detail", args=[order_number])
        )

        self.assertEqual(response.status_code, 404)


class CustomerReturnRequestTests(OrderTestBase):
    """Customers request returns from a delivered order and track the outcome."""

    def setUp(self):
        super().setUp()
        self.make_guest_cart(quantity=2)
        self.assertEqual(self.post_checkout(self.client).status_code, 201)
        self.order = Order.objects.get()
        self.item = self.order.items.get()
        OrderService.update_status(self.order.pk, OrderStatus.DELIVERED)
        self.order.refresh_from_db()

    def post_return_request(self, *, items=None, client=None, reason="Too small"):
        payload = {
            "reason": reason,
            "items": items or [{"item_id": self.item.pk, "quantity": 1}],
        }
        return (client or self.client).post(
            reverse("orders:order-return-request", args=[self.order.order_number]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_customer_can_request_a_return_for_a_delivered_order(self):
        response = self.post_return_request()

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], ReturnRequestStatus.REQUESTED)
        self.assertEqual(body["total_quantity"], 1)
        self.assertEqual(body["items"][0]["item_id"], self.item.pk)

        return_request = ReturnRequest.objects.get(order=self.order)
        self.assertEqual(return_request.reason, "Too small")
        self.assertIsNone(return_request.requested_by_id)
        # A request is intent only: nothing is restocked until staff approve.
        self.record.refresh_from_db()
        self.assertEqual(self.record.quantity_on_hand, 8)
        self.item.refresh_from_db()
        self.assertEqual(self.item.returned_quantity, 0)

    def test_order_detail_tracks_history_and_return_requests(self):
        self.post_return_request()

        response = self.client.get(
            reverse("orders:order-detail", args=[self.order.order_number])
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["can_request_return"])
        self.assertEqual(
            body["status_history"][-1]["new_status"], OrderStatus.DELIVERED
        )
        self.assertEqual(
            body["return_requests"][0]["status"], ReturnRequestStatus.REQUESTED
        )
        self.assertEqual(body["items"][0]["remaining_quantity"], 2)

    def test_return_request_requires_a_delivered_order(self):
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.SHIPPED)

        response = self.post_return_request()

        self.assertEqual(response.status_code, 400)
        self.assertIn("delivered", response.json()["detail"].lower())
        self.assertFalse(ReturnRequest.objects.exists())

    def test_over_quantity_request_is_rejected(self):
        response = self.post_return_request(
            items=[{"item_id": self.item.pk, "quantity": 3}]
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("only 2", response.json()["detail"].lower())
        self.assertFalse(ReturnRequest.objects.exists())

    def test_a_second_open_request_is_rejected(self):
        self.assertEqual(self.post_return_request().status_code, 201)

        response = self.post_return_request()

        self.assertEqual(response.status_code, 400)
        self.assertIn("already", response.json()["detail"].lower())
        self.assertEqual(ReturnRequest.objects.count(), 1)

    def test_other_session_cannot_request_a_return(self):
        response = self.post_return_request(client=Client())

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ReturnRequest.objects.exists())

    def test_authenticated_customer_request_is_attributed_to_their_account(self):
        user = User.objects.create_user(
            email="buyer@example.com", password="ValidPassword123!"
        )
        self.order.user = user
        self.order.session_key = ""
        self.order.save(update_fields=["user", "session_key", "updated_at"])
        self.client.force_login(user)

        response = self.post_return_request()

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(ReturnRequest.objects.get().requested_by, user)
