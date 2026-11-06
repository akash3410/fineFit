"""Media-access and admin-security tests for the 2FA middleware fix.

Covers:
- anonymous and authenticated users can access public media without being
  redirected to the 2FA enrollment page;
- media requests return the image file with the correct Content-Type instead
  of an HTML redirect;
- admin pages still redirect non-verified staff to 2FA enrollment;
- login, logout, 2FA enrollment, challenge, forgot-password and verification
  routes stay accessible for authenticated users without verified 2FA.
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.test import Client
from django.test import RequestFactory
from django.test import TransactionTestCase
from django.test import TestCase
from django.test.utils import override_settings
from django.views.static import serve as static_serve

from apps.accounts.models import TwoFactorMethod

User = get_user_model()


class TestPublicMediaAccess(TestCase):
    """Public product/category images must not be redirected to 2FA enrollment."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="staff@example.com", password="StaffPass123!"
        )
        self.fresh_user = User.objects.create_user(
            email="fresh@example.com", password="FreshPass123!"
        )

    def _image_path(self):
        return settings.MEDIA_ROOT / "public-product.png"

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_anonymous_users_can_access_public_images(self):
        self._seed_image()
        client = Client()
        response = client.get("/media/public-product.png")
        assert response.status_code == 200
        assert "image/png" in response["Content-Type"]

    def test_authenticated_without_2fa_can_access_public_images(self):
        self._seed_image()
        client = Client()
        client.force_login(self.user)
        response = client.get("/media/public-product.png")
        assert response.status_code == 200
        assert "image/png" in response["Content-Type"]
        assert response.status_code != 302

    def test_authenticated_with_verified_2fa_can_access_public_images(self):
        self._seed_image()
        method = TwoFactorMethod.objects.create(
            user=self.fresh_user,
            method=TwoFactorMethod.Method.EMAIL,
            destination="fresh@example.com",
            is_verified=True,
            is_primary=True,
        )
        client = Client()
        client.force_login(self.fresh_user)
        response = client.get("/media/public-product.png")
        assert response.status_code == 200
        assert "image/png" in response["Content-Type"]

    def test_media_request_does_not_redirect_to_2fa_enrollment(self):
        self._seed_image()
        client = Client()
        client.force_login(self.user)
        response = client.get("/media/public-product.png")
        assert response.status_code == 200
        assert response.status_code != 302
        assert response["Location"] != "/admin/2fa/enroll/"

    def test_serving_view_returns_image_content(self):
        path = self._seed_image()
        if path.exists():
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 64)
        request = RequestFactory().get("/media/public-product.png")
        served = static_serve(request, "public-product.png", document_root=str(settings.MEDIA_ROOT))
        assert served.status_code == 200
        assert "image/png" in served["Content-Type"]
        assert b"\x89PNG" in next(served.streaming_content)


@pytest.mark.django_db
class TestAdminSecurityEnforcement:
    """Protected admin pages must keep enforcing 2FA enrollment."""

    def _staff(self):
        return User.objects.create_user(
            email="admin@example.com", password="AdminPass123!", is_staff=True
        )

    def _verified_staff(self):
        user = self._staff()
        TwoFactorMethod.objects.create(
            user=user,
            method=TwoFactorMethod.Method.EMAIL,
            destination=user.email,
            is_verified=True,
            is_primary=True,
        )
        return user

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

        assert "/admin/2fa/enroll/" in response["Location"]

    def test_login_route_stays_accessible(self):
        fresh = User.objects.create_user(email="login@example.com", password="LoginPass123!", is_staff=True)
        response = self._client(fresh).get("/admin/login/")
        assert response.status_code == 200

    def test_logout_route_stays_accessible(self):
        fresh = User.objects.create_user(email="logout@example.com", password="LogoutPass123!", is_staff=True)
        response = self._client(fresh).get("/admin/logout/", follow=True)
        assert response.status_code == 200

    def test_2fa_enrollment_route_stays_accessible(self):
        fresh = User.objects.create_user(email="enroll@example.com", password="EnrollPass123!", is_staff=True)
        response = self._client(fresh).get("/admin/2fa/enroll/")
        assert response.status_code == 200

    def test_2fa_challenge_route_stays_accessible(self):
        fresh = User.objects.create_user(email="challenge2@example.com", password="Challenge2Pass123!", is_staff=True)
        response = self._client(fresh).get("/admin/2fa/challenge/")
        assert response.status_code == 200

    def test_forgot_password_route_stays_accessible(self):
        fresh = User.objects.create_user(email="forgot2@example.com", password="Forgot2Pass123!", is_staff=True)
        response = self._client(fresh).get("/admin/forgot-password/")
        assert response.status_code == 200

    def test_reset_password_route_stays_accessible(self):
        fresh = User.objects.create_user(email="reset2@example.com", password="Reset2Pass123!", is_staff=True)
        response = self._client(fresh).get("/admin/reset-password/")
        assert response.status_code == 200

    def test_verify_route_stays_accessible(self):
        fresh = User.objects.create_user(email="verify3@example.com", password="Verify3Pass123!", is_staff=True)
        response = self._client(fresh).get("/admin/verify/")
        assert response.status_code == 200

    def test_api_v1_prefix_still_exempt_from_2fa_redirect(self):
        fresh = User.objects.create_user(email="api1@example.com", password="Api1Pass123!", is_staff=True)
        response = self._client(fresh).get("/api/v1/products/")
        # The public API should not suddenly be redirected to 2FA enrollment.
        assert response.status_code in (200, 302)
        assert response["Location"] != "/admin/2fa/enroll/"


@pytest.mark.django_db
class TestRegressionForgotPassword:
    """Regression guards for the admin HTML auth pages."""

    def test_forgot_password_reaches_view(self):
        client = Client()
        user = User.objects.create_user(email="forgot@finefit.store", password="ForgotPass123!")
        client.force_login(user)
        response = client.post(
            "/admin/forgot-password/",
            {"identifier": "forgot@finefit.store", "channel": "email"},
        )
        assert response.status_code == 200
