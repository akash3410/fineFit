from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    """
    Ensure a CSRF cookie is set in the client's browser for session-authenticated API requests.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        csrf_token = get_token(request)
        return Response({"detail": "CSRF cookie set", "csrfToken": csrf_token})


class CurrentUserView(APIView):
    """
    Retrieve the authenticated user's profile.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class SessionLoginView(APIView):
    """
    Authenticate user via session credentials and set session cookie.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = email.strip().lower()
        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid credentials provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "This user account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ADR-005 / ADR-010 (Option B): capture the guest session key BEFORE
        # ``login()`` — Django rotates the session key on login for
        # session-fixation protection, and the guest cart is keyed by the
        # pre-login session key. Merge happens only after successful
        # authentication, inside a transaction, and never on failure.
        guest_session_key = request.session.session_key

        login(request, user)

        merge_result = None
        if guest_session_key:
            try:
                from apps.cart.services import CartService

                # Deferred import avoids a hard coupling between accounts and
                # the cart domain (works even if apps.cart is unavailable).
                user_cart, conflicts = CartService.merge_guest_cart_into_user_cart(
                    guest_session_key=guest_session_key,
                    user=user,
                )
                merge_result = {
                    "cart_id": str(user_cart.id),
                    "total_quantity": user_cart.total_quantity,
                    "conflicts": conflicts,
                }
            except Exception as exc:  # noqa: BLE001
                # A merge failure must never block or roll back a successful
                # login, and must never destroy the guest cart (the merge
                # transaction rolled back, so the guest cart is intact).
                logger.warning(
                    "Guest cart merge failed after successful login: %s", exc
                )

        serializer = UserSerializer(user)
        response_data = serializer.data
        if merge_result is not None:
            response_data = {**serializer.data, "cart_merge": merge_result}
        return Response(response_data)


class SessionLogoutView(APIView):
    """
    Log out the currently authenticated session.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Successfully logged out."})
