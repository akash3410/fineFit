"""
Middleware to enforce two-factor authentication for all authenticated users.

After a user logs in via session, if they have no verified TwoFactorMethod,
they are redirected to the 2FA enrollment page before accessing any admin page.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Paths that do not require 2FA enrollment (exempt from middleware redirect)
EXEMPT_PATHS = [
    "/admin/login/",
    "/admin/logout/",
    "/admin/2fa/enroll/",
    "/admin/2fa/challenge/",
    "/admin/forgot-password/",
    "/admin/reset-password/",
    "/admin/verify/",
    "/admin/",
    "/api/v1/",
]


class TwoFactorRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Only enforce for authenticated users with a session
        if not request.user or not request.user.is_authenticated:
            return None

        path = request.path

        # Skip exempt paths
        if any(path == p or path.startswith(p) for p in EXEMPT_PATHS):
            return None

        # Check if user has a verified 2FA method
        has_2fa = request.user.two_factor_methods.filter(is_verified=True).exists()
        if not has_2fa:
            enroll_url = reverse("admin_panel:2fa_enroll")
            if path != enroll_url:
                return redirect(enroll_url)

        return None
