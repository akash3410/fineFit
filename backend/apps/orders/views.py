"""Order REST API views.

Ownership resolution mirrors the cart: authenticated customers are identified by
their session user, guests by their Django session key. Order numbers are never
sufficient on their own — every lookup is filtered by that server-side owner.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.authentication import CartSessionAuthentication
from apps.cart.services import CartService

from .exceptions import OrderError
from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderReadSerializer,
    ReturnRequestCreateSerializer,
    ReturnRequestReadSerializer,
)
from .services import OrderService


class OrderBaseView(APIView):
    """Shared CSRF-enforcing session auth and ownership resolution."""

    authentication_classes = [CartSessionAuthentication]
    permission_classes = [permissions.AllowAny]

    def owner_filter(self, request) -> dict | None:
        """Filter kwargs for the current owner, or None when unidentifiable."""
        if request.user.is_authenticated:
            return {"user": request.user}
        session_key = request.session.session_key
        if not session_key:
            return None
        return {"user__isnull": True, "session_key": session_key}


class OrderCheckoutView(OrderBaseView):
    """POST the current cart to place a cash-on-delivery order."""

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if request.user.is_authenticated:
            cart = CartService.get_cart(user=request.user)
            user, session_key = request.user, ""
        else:
            session_key = request.session.session_key or ""
            cart = (
                CartService.get_cart(session_key=session_key)
                if session_key
                else None
            )
            user = None

        try:
            order = OrderService.place_order(
                cart,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                customer_email=data.get("customer_email", ""),
                shipping_address=data["shipping_address"],
                notes=data.get("notes", ""),
                payment_method=data["payment_method"],
                user=user,
                session_key=session_key,
            )
        except OrderError as err:
            return Response(
                {"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            OrderReadSerializer(order).data, status=status.HTTP_201_CREATED
        )


class OrderListView(OrderBaseView):
    """GET the current owner's order history (newest first)."""

    def get(self, request):
        filters = self.owner_filter(request)
        if filters is None:
            return Response({"results": []})
        orders = (
            Order.objects.filter(**filters)
            .prefetch_related(
                "items",
                "status_changes",
                "return_requests__items__order_item",
            )
            .order_by("-created_at")
        )
        return Response({"results": OrderReadSerializer(orders, many=True).data})


class OrderDetailView(OrderBaseView):
    """GET a single order by its customer-facing number."""

    def get(self, request, order_number: str):
        filters = self.owner_filter(request)
        if filters is None:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        order = (
            Order.objects.filter(order_number=order_number, **filters)
            .prefetch_related(
                "items",
                "status_changes",
                "return_requests__items__order_item",
            )
            .first()
        )
        if order is None:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderReadSerializer(order).data)


class OrderReturnRequestView(OrderBaseView):
    """POST a line-level return request for an order owned by the caller."""

    def post(self, request, order_number: str):
        filters = self.owner_filter(request)
        if filters is None:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )
        order = Order.objects.filter(order_number=order_number, **filters).first()
        if order is None:
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = ReturnRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quantities = {
            item["item_id"]: item["quantity"] for item in data["items"]
        }

        try:
            return_request = OrderService.request_return(
                order.pk,
                quantities,
                requested_by=(
                    request.user if request.user.is_authenticated else None
                ),
                reason=data.get("reason", ""),
            )
        except OrderError as err:
            return Response(
                {"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            ReturnRequestReadSerializer(return_request).data,
            status=status.HTTP_201_CREATED,
        )
