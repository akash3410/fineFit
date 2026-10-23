"""
PostgreSQL-backed integration tests for CustomUser, authentication, and CSRF protection.
"""

import pytest
from django.db import IntegrityError, transaction
from django.test import Client

from apps.accounts.models import CustomUser


@pytest.mark.django_db
class TestCustomUserDatabaseIntegration:
    """Integration tests verifying database-level persistence and constraints."""

    def test_custom_user_creation_and_retrieval(self):
        """Verify CustomUser can be inserted into PostgreSQL and retrieved by email."""
        user = CustomUser.objects.create_user(
            email="Shopper.Fashion@FineFit.STORE",
            password="StrongPassword123!",
            first_name="Elena",
            last_name="Rostova",
        )

        # Retrieve user from the database
        retrieved = CustomUser.objects.get(email="shopper.fashion@finefit.store")
        assert retrieved.id == user.id
        assert retrieved.email == "shopper.fashion@finefit.store"
        assert retrieved.first_name == "Elena"
        assert retrieved.last_name == "Rostova"
        assert retrieved.check_password("StrongPassword123!") is True
        assert retrieved.is_active is True
        assert retrieved.is_staff is False
        assert retrieved.is_superuser is False

    def test_database_enforces_case_insensitive_unique_constraint(self):
        """
        Verify that PostgreSQL raises IntegrityError when attempting to insert
        a duplicate email differing only in casing (unique_case_insensitive_email).
        """
        CustomUser.objects.create_user(
            email="luxury@finefit.store",
            password="PasswordOne123!",
        )

        # Test database constraint failure within an atomic block to allow clean rollback
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                # Raw insert or direct creation attempting to bypass Python-level normalization
                CustomUser.objects.bulk_create([
                    CustomUser(
                        email="LUXURY@finefit.store",
                        is_active=True,
                    )
                ])


@pytest.mark.django_db
class TestSessionAuthenticationAndCSRFIntegration:
    """Integration tests verifying session login/logout and CSRF enforcement."""

    def test_session_login_and_logout_flow(self):
        """Verify full browser session authentication lifecycle."""
        client = Client()
        user = CustomUser.objects.create_user(
            email="testuser@finefit.store",
            password="ValidSessionPass123!",
            first_name="Marcus",
            last_name="Vance",
        )

        # 1. Fetch CSRF cookie
        csrf_response = client.get("/api/v1/auth/csrf/")
        assert csrf_response.status_code == 200
        csrf_token = csrf_response.cookies.get("csrftoken").value
        assert csrf_token is not None

        # 2. Login with mixed-case email (verifying case-insensitive login)
        login_response = client.post(
            "/api/v1/auth/login/",
            data={"email": "TestUser@FineFit.store", "password": "ValidSessionPass123!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        assert login_response.status_code == 200
        assert login_response.json()["email"] == "testuser@finefit.store"
        assert client.session["_auth_user_id"] == str(user.id)

        # 3. Retrieve authenticated user profile
        me_response = client.get("/api/v1/auth/me/")
        assert me_response.status_code == 200
        assert me_response.json()["id"] == str(user.id)

        # 4. Logout
        logout_response = client.post(
            "/api/v1/auth/logout/",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        assert logout_response.status_code == 200

        # 5. Verify session is terminated
        me_after_logout = client.get("/api/v1/auth/me/")
        assert me_after_logout.status_code == 403

    def test_csrf_enforcement_on_state_changing_requests(self):
        """Verify that state-changing authenticated requests reject calls missing CSRF tokens."""
        client = Client(enforce_csrf_checks=True)

        user = CustomUser.objects.create_user(
            email="member@finefit.store",
            password="MemberPassword123!",
        )

        # 1. Fetch CSRF token and authenticate session
        csrf_response = client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.cookies.get("csrftoken").value
        login_res = client.post(
            "/api/v1/auth/login/",
            data={"email": "member@finefit.store", "password": "MemberPassword123!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        assert login_res.status_code == 200

        # 2. Issue a state-changing authenticated request (logout) WITHOUT CSRF token
        unprotected_response = client.post("/api/v1/auth/logout/")
        assert unprotected_response.status_code == 403
        assert "CSRF Failed" in unprotected_response.json()["detail"]
