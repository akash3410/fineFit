"""
Tests for the CustomUser admin configuration.

Covers the registration of CustomUserAdmin and guards against a save-time
regression where editable ``date_joined``/``last_login`` fields caused a
confusing "This field is required" error when staff cleared them.
"""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client

from apps.accounts.admin import CustomUserAdmin
from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


class TestCustomUserAdminRegistration:
    """Verify CustomUser is registered with the custom admin class."""

    def test_custom_user_is_registered(self):
        assert CustomUser in admin.site._registry

    def test_registered_admin_class_is_custom(self):
        assert isinstance(admin.site._registry[CustomUser], CustomUserAdmin)

    def test_audit_timestamps_are_readonly(self):
        """Auto-managed timestamps must not be staff-editable.

        Editable ``date_joined`` (no ``blank=True``) lets staff clear the
        field and break the save with "This field is required".
        """
        assert CustomUserAdmin.readonly_fields == ("last_login", "date_joined")


class TestCustomUserAdminChangeForm:
    """Exercise the admin change form as a logged-in superuser."""

    @pytest.fixture()
    def superuser(self):
        return CustomUser.objects.create_superuser("admin@example.com", "Adm1nStr0ng!")

    @pytest.fixture()
    def admin_client(self, superuser):
        client = Client()
        client.force_login(superuser)
        return client

    def test_change_page_renders(self, admin_client, superuser):
        response = admin_client.get(
            f"/admin/accounts/customuser/{superuser.pk}/change/"
        )
        assert response.status_code == 200

    def test_change_page_renders_audit_fields_readonly(self, admin_client, superuser):
        """``date_joined``/``last_login`` must render as text, not inputs."""
        body = admin_client.get(
            f"/admin/accounts/customuser/{superuser.pk}/change/"
        ).content.decode()
        assert 'name="date_joined_0"' not in body
        assert 'name="last_login_0"' not in body

    def test_save_without_date_joined_succeeds(self, admin_client, superuser):
        """Saving without posting audit timestamps must not fail.

        This is the regression guard: previously ``date_joined`` was a
        required form field, so clearing it returned a 200 with
        "This field is required" instead of saving.
        """
        response = admin_client.post(
            f"/admin/accounts/customuser/{superuser.pk}/change/",
            {
                "email": "admin@example.com",
                "password": superuser.password,
                "first_name": "Updated",
                "last_name": "Name",
                "phone_number": "",
                "is_active": "on",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )
        assert response.status_code == 302
        superuser.refresh_from_db()
        assert superuser.first_name == "Updated"
        # The audit timestamp must remain untouched.
        assert superuser.date_joined is not None

    def test_add_user_page_renders(self, admin_client):
        response = admin_client.get("/admin/accounts/customuser/add/")
        assert response.status_code == 200

    def test_add_user_creates_usable_account(self, admin_client):
        """A user created through the admin must be able to log in."""
        response = admin_client.post(
            "/admin/accounts/customuser/add/",
            {
                "email": "staff@example.com",
                "password1": "Str0ngPass!9x",
                "password2": "Str0ngPass!9x",
                "is_staff": "on",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        assert CustomUser.objects.filter(email="staff@example.com").exists()
        assert Client().login(email="staff@example.com", password="Str0ngPass!9x")
