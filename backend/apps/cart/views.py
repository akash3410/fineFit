"""
Cart REST API views.

Ownership resolution
--------------------
The cart owner is ALWAYS derived from server-side request identity:
  - authenticated requests -> the logged-in customer's cart
  - anonymous requests     -> the Django session-key guest cart

Guest sessions are created lazily the first time a guest needs a cart. Session
keys and user IDs are never read from request payloads and never included in
responses (no exposure of session identifiers).

CSRF
----
Write endpoints (POST/PATCH/DELETE/PUT) are CSRF-protected for BOTH
authenticated customers and anonymous guests via ``CartSessionAuthentication``
(DRF alone only protects authenticated writes).
"""

from django.db.models import Prefetch
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import CartSessionAuthentication
from .exceptions import (
    CartItemNotFoundError,
    CartValidationError,
)
from .models import Cart, CartItem
from .serializers import (
    AddCartItemSerializer,
    CartSerializer,
    UpdateCartItemSerializer,
)
from .services import CartService


class CartBaseView(APIView):
    """Shared cart resolution for all cart endpoints."""

    # Cart-specific auth: CSRF is enforced for anonymous guest writes too
    # (DRF's stock SessionAuthentication only protects authenticated writes).
    authentication_classes = [CartSessionAuthentication]
    permission_classes = [permissions.AllowAny]

    def get_cart_serializer_context(self):
        return {"request": self.request}

    def _prefetched_items(self):
        return CartItem.objects.select_related(
            "variant__product", "variant__stock_record"
        ).prefetch_related("variant__product__images")

    def get_cart(self, request, *, auto_create: bool = False):
        """
        Resolve the current cart for the request identity.

        Returns ``(cart, guest_session_needs_save)``; ``cart`` is None when the
        requester has no cart yet and ``auto_create`` is False.
        """
        if request.user.is_authenticated:
            if auto_create:
                cart = CartService.get_or_create_cart(user=request.user)
            else:
                cart = CartService.get_cart(user=request.user)
            return cart, False

        # --- Guest identity: derive strictly from the server-side session ---
        session = request.session
        if not session.session_key and not auto_create:
            # Guest has no session yet -> no guest cart can exist.
            return None, False
        if auto_create and not session.session_key:
            # Persist a session so the guest cart has a stable owner.
            session.create()
        if auto_create:
            cart = CartService.get_or_create_cart(
                session_key=session.session_key
            )
        else:
            cart = CartService.get_cart(session_key=session.session_key)
        return cart, auto_create

    def serialize_cart(self, cart) -> Response:
        # Re-fetch with optimized relations so item serialization avoids N+1.
        cart = (
            Cart.objects.prefetch_related(
                Prefetch("items", queryset=self._prefetched_items())
            )
            .get(pk=cart.pk)
        )
        serializer = CartSerializer(
            cart, context=self.get_cart_serializer_context()
        )
        return Response(serializer.data)


class CartDetailView(CartBaseView):
    """Retrieve the current cart (GET) or clear it (DELETE)."""

    def get(self, request):
        cart, _ = self.get_cart(request, auto_create=True)
        return self.serialize_cart(cart)

    def delete(self, request):
        """Clear the current cart, leaving the cart row intact."""
        cart, _ = self.get_cart(request)
        if cart is not None:
            cart = CartService.clear_cart(cart)
            return self.serialize_cart(cart)
        # No cart yet: nothing to clear; report an empty cart state.
        cart, _ = self.get_cart(request, auto_create=True)
        return self.serialize_cart(cart)


class CartClearView(CartBaseView):
    """Clear every line item from the current cart (POST alternative to DELETE)."""

    def post(self, request):
        cart, _ = self.get_cart(request)
        if cart is not None:
            cart = CartService.clear_cart(cart)
            return self.serialize_cart(cart)
        cart, _ = self.get_cart(request, auto_create=True)
        return self.serialize_cart(cart)


class CartItemAddView(CartBaseView):
    """Add a variant (by trusted reference) with a server-validated quantity."""

    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = self.get_cart(request, auto_create=True)
        sanitized = CartSerializer(
            cart, context=self.get_cart_serializer_context()
        )
        try:
            updated_cart = CartService.add_item(
                cart,
                variant_or_id=serializer.validated_data["variant_id"],
                quantity=serializer.validated_data["quantity"],
            )
        except CartValidationError as err:
            # Refresh cart state so the storefront still shows current lines.
            cart.refresh_from_db(fields=["updated_at"])
            return Response(
                {"detail": str(err), "cart": sanitized.data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out_serializer = CartSerializer(
            updated_cart, context=self.get_cart_serializer_context()
        )
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class CartItemDetailView(CartBaseView):
    """Update (PATCH) or remove (DELETE) a single cart line."""

    def patch(self, request, identifier):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = self.get_cart(request, auto_create=True)
        try:
            updated_cart = CartService.update_item_quantity(
                cart,
                identifier=identifier,
                quantity=serializer.validated_data["quantity"],
            )
        except (CartItemNotFoundError, CartValidationError) as err:
            return Response(
                {"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )
        out_serializer = CartSerializer(
            updated_cart, context=self.get_cart_serializer_context()
        )
        return Response(out_serializer.data)

    def put(self, request, identifier):
        """PUT is not supported for partial quantity updates."""
        return Response(
            {"detail": "Use PATCH to update the cart item quantity."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def delete(self, request, identifier):
        cart, _ = self.get_cart(request, auto_create=True)
        try:
            updated_cart = CartService.remove_item(cart, identifier=identifier)
        except (CartItemNotFoundError, CartValidationError) as err:
            return Response(
                {"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )
        out_serializer = CartSerializer(
            updated_cart, context=self.get_cart_serializer_context()
        )
        return Response(out_serializer.data)
