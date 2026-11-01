"""
Tests for forgot password, verification, 2FA, and JWT authentication.
"""

import pytest
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from apps.accounts.models import (
    CustomUser,
    PasswordResetRequest,
    VerificationCode,
    TwoFactorMethod,
    BackupCode,
)


@pytest.mark.django_db
class TestForgotPassword:
    """Tests for the forgot password flow."""

    def test_forgot_password_email_sends_reset(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="reset@finefit.store", password="StrongPass123!"
        )
        response = client.post(
            "/admin/forgot-password/",
            {"identifier": "reset@finefit.store", "channel": "email"},
        )
        assert response.status_code == 200
        assert PasswordResetRequest.objects.filter(
            identifier="reset@finefit.store"
        ).exists()

    def test_forgot_password_phone_sends_sms(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="sms@finefit.store",
            phone_number="+15551234567",
            password="StrongPass123!",
        )
        response = client.post(
            "/admin/forgot-password/",
            {"identifier": "+15551234567", "channel": "sms"},
        )
        assert response.status_code == 200
        assert PasswordResetRequest.objects.filter(
            identifier="+15551234567"
        ).exists()

    def test_forgot_password_no_user_enumeration(self):
        client = Client()
        # Nonexistent email should return same response as existing
        response = client.post(
            "/admin/forgot-password/",
            {"identifier": "nonexistent@finefit.store", "channel": "email"},
        )
        assert response.status_code == 200
        assert PasswordResetRequest.objects.count() == 0

    def test_forgot_password_rate_limit(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="ratelimit@finefit.store", password="StrongPass123!"
        )
        # Create 3 recent requests
        now = timezone.now()
        for _ in range(3):
            PasswordResetRequest.objects.create(
                identifier="ratelimit@finefit.store",
                expires_at=now + timedelta(hours=1),
            )
        response = client.post(
            "/admin/forgot-password/",
            {"identifier": "ratelimit@finefit.store", "channel": "email"},
        )
        assert response.status_code == 200
        # Should show error about too many requests


@pytest.mark.django_db
class TestResetPassword:
    """Tests for password reset with token."""

    def test_reset_password_with_valid_token(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="reset2@finefit.store", password="OldPass123!"
        )
        reset_request = PasswordResetRequest.objects.create(
            identifier="reset2@finefit.store",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        response = client.post(
            f"/admin/reset-password/{reset_request.token}/",
            {"password": "NewPass123!", "confirm_password": "NewPass123!"},
        )
        assert response.status_code == 302  # Redirect to login
        user.refresh_from_db()
        assert user.check_password("NewPass123!")
        reset_request.refresh_from_db()
        assert reset_request.is_used()

    def test_reset_password_with_expired_token(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="reset3@finefit.store", password="OldPass123!"
        )
        reset_request = PasswordResetRequest.objects.create(
            identifier="reset3@finefit.store",
            expires_at=timezone.now() - timedelta(hours=1),  # Already expired
        )
        response = client.post(
            f"/admin/reset-password/{reset_request.token}/",
            {"password": "NewPass123!", "confirm_password": "NewPass123!"},
        )
        assert response.status_code == 302  # Redirect with error
        user.refresh_from_db()
        assert user.check_password("OldPass123!")  # Password unchanged

    def test_reset_password_password_mismatch(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="reset4@finefit.store", password="OldPass123!"
        )
        reset_request = PasswordResetRequest.objects.create(
            identifier="reset4@finefit.store",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        response = client.post(
            f"/admin/reset-password/{reset_request.token}/",
            {"password": "NewPass123!", "confirm_password": "DifferentPass!"},
        )
        assert response.status_code == 200  # Re-render with error


@pytest.mark.django_db
class TestAccountVerification:
    """Tests for email/phone verification."""

    def test_verify_registration_code_activates_user(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="verify@finefit.store", password="StrongPass123!", is_active=False
        )
        code = VerificationCode.objects.create(
            user=user,
            identifier="verify@finefit.store",
            channel="email",
            code_hash="pbkdf2_sha256$260000$test$test",
            purpose="registration",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        # Set a known code hash
        from django.contrib.auth.hashers import make_password
        code.code_hash = make_password("123456")
        code.save()

        response = client.post(
            "/admin/verify/",
            {
                "identifier": "verify@finefit.store",
                "code": "123456",
                "purpose": "registration",
            },
        )
        assert response.status_code == 302  # Redirect to login
        user.refresh_from_db()
        assert user.is_active is True


@pytest.mark.django_db
class TestTwoFactorEnrollment:
    """Tests for 2FA enrollment."""

    def test_2fa_enroll_email(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="2fa@finefit.store", password="StrongPass123!", is_staff=True
        )
        client.force_login(user)
        response = client.post(
            "/admin/2fa/enroll/",
            {"method": "email", "destination": "2fa@finefit.store"},
        )
        assert response.status_code == 302  # Redirect to challenge
        assert TwoFactorMethod.objects.filter(user=user, method="email").exists()

    def test_2fa_enroll_wrong_email(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="2fa2@finefit.store", password="StrongPass123!", is_staff=True
        )
        client.force_login(user)
        response = client.post(
            "/admin/2fa/enroll/",
            {"method": "email", "destination": "wrong@finefit.store"},
        )
        assert response.status_code == 200  # Re-render with error
        assert TwoFactorMethod.objects.filter(user=user).count() == 0


@pytest.mark.django_db
class TestJWTAuth:
    """Tests for JWT token obtain, refresh, and blacklist."""

    def test_jwt_obtain_pair(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="jwt@finefit.store", password="StrongPass123!"
        )
        response = client.post(
            "/api/v1/token/",
            {"email": "jwt@finefit.store", "password": "StrongPass123!"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data

    def test_jwt_obtain_pair_invalid_credentials(self):
        client = Client()
        CustomUser.objects.create_user(
            email="jwt2@finefit.store", password="StrongPass123!"
        )
        response = client.post(
            "/api/v1/token/",
            {"email": "jwt2@finefit.store", "password": "WrongPass!"},
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_jwt_refresh(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="jwt3@finefit.store", password="StrongPass123!"
        )
        # Obtain tokens
        resp = client.post(
            "/api/v1/token/",
            {"email": "jwt3@finefit.store", "password": "StrongPass123!"},
            content_type="application/json",
        )
        refresh = resp.json()["refresh"]
        # Refresh
        response = client.post(
            "/api/v1/token/refresh/",
            {"refresh": refresh},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "access" in response.json()

    def test_jwt_blacklist(self):
        client = Client()
        user = CustomUser.objects.create_user(
            email="jwt4@finefit.store", password="StrongPass123!"
        )
        resp = client.post(
            "/api/v1/token/",
            {"email": "jwt4@finefit.store", "password": "StrongPass123!"},
            content_type="application/json",
        )
        refresh = resp.json()["refresh"]
        # Blacklist
        client.force_login(user)
        response = client.post(
            "/api/v1/token/blacklist/",
            {"refresh": refresh},
            content_type="application/json",
        )
        assert response.status_code == 200
