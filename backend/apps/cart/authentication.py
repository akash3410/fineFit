"""
Cart-specific session authentication with CSRF enforcement for guest writes.

Background: DRF's stock ``SessionAuthentication`` only enforces CSRF for
*authenticated* requests (it returns early for anonymous users), and DRF views
are wrapped in Django's ``csrf_exempt`` so ``CsrfViewMiddleware`` never checks
them at the middleware layer. Guest cart write endpoints (POST / PATCH /
DELETE) would therefore be unprotected against cross-site attacks.

``CartSessionAuthentication`` restores those guarantees:
  - Authenticated users authenticate through the standard session mechanism,
    including the regular CSRF enforcement.
  - Anonymous guest requests on unsafe methods are explicitly CSRF-checked
    here, ensuring the same ``X-CSRFToken`` / ``csrftoken`` contract that
    authenticated customers already follow.

Permissions remain controlled by the view (``AllowAny`` on cart endpoints is
safe only because ownership is always derived from the server-side session/
user, never from payload data).
"""

from rest_framework.authentication import SessionAuthentication

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class CartSessionAuthentication(SessionAuthentication):
    """Session authentication that enforces CSRF for guest cart writes."""

    def authenticate(self, request):
        user = getattr(request._request, "user", None)
        if user is not None and user.is_active and user.is_authenticated:
            # Standard, secure session authentication (includes CSRF checks).
            return super().authenticate(request)

        # Anonymous / inactive user: no credentials to establish, but unsafe
        # methods must still pass an explicit CSRF verification.
        if request.method not in SAFE_METHODS:
            self.enforce_csrf(request)
        return None
