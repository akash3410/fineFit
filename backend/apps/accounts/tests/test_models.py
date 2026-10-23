"""
Tests for CustomUser model, CustomUserManager, and authentication configuration.
"""

import uuid
from unittest.mock import MagicMock, patch
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Lower

from apps.accounts.models import CustomUser


class TestAuthenticationModelConfiguration:
    """Tests verifying the authentication model configuration in Django."""

    def test_auth_user_model_is_configured(self):
        """Verify AUTH_USER_MODEL is set to accounts.CustomUser."""
        assert settings.AUTH_USER_MODEL == "accounts.CustomUser"

    def test_get_user_model_returns_custom_user(self):
        """Verify get_user_model() resolves to CustomUser class."""
        assert get_user_model() is CustomUser

    def test_username_field_is_email(self):
        """Verify the authentication identifier is the email field."""
        assert CustomUser.USERNAME_FIELD == "email"

    def test_required_fields_is_empty(self):
        """Verify REQUIRED_FIELDS has no username and prompts for email and password."""
        assert CustomUser.REQUIRED_FIELDS == []

    def test_username_field_does_not_exist_on_model(self):
        """Verify the legacy username field is removed from the model schema."""
        field_names = [f.name for f in CustomUser._meta.get_fields()]
        assert "username" not in field_names


class TestCustomUserModelSchema:
    """Tests verifying model schema constraints and field definitions."""

    def test_uuid_primary_key_definition(self):
        """Verify id is a non-editable UUIDField primary key with uuid.uuid4 default."""
        pk_field = CustomUser._meta.get_field("id")
        assert isinstance(pk_field, models.UUIDField)
        assert pk_field.primary_key is True
        assert pk_field.editable is False
        assert pk_field.default == uuid.uuid4

    def test_email_field_is_unique(self):
        """Verify email field has unique=True constraint defined."""
        email_field = CustomUser._meta.get_field("email")
        assert isinstance(email_field, models.EmailField)
        assert email_field.unique is True

    def test_case_insensitive_unique_constraint_defined(self):
        """
        Verify database-level UniqueConstraint on Lower('email') exists in Meta constraints.
        """
        constraints = CustomUser._meta.constraints
        unique_constraints = [c for c in constraints if isinstance(c, models.UniqueConstraint)]
        assert any(c.name == "unique_case_insensitive_email" for c in unique_constraints)

        constraint = next(c for c in unique_constraints if c.name == "unique_case_insensitive_email")
        # Check that Lower('email') expression is in the constraint expressions
        assert len(constraint.expressions) == 1
        assert isinstance(constraint.expressions[0], Lower)
        assert constraint.expressions[0].source_expressions[0].name == "email"

    def test_user_string_representation(self):
        """Verify __str__ returns the user email."""
        user = CustomUser(email="shopper@finefit.store")
        assert str(user) == "shopper@finefit.store"

    def test_uuid_primary_key_generated_on_instantiation(self):
        """Verify a valid UUID4 is generated for newly instantiated user objects."""
        user = CustomUser(email="test@finefit.store")
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)

    def test_model_clean_strips_and_lowercases_email(self):
        """Verify model clean() method strips whitespace and normalizes email to lowercase."""
        user = CustomUser(email="   SHOPPER@FineFit.STORE   ")
        user.clean()
        assert user.email == "shopper@finefit.store"

    @patch.object(models.Model, "save")
    def test_model_save_strips_and_lowercases_email(self, mock_super_save):
        """Verify model save() method normalizes email even if clean() was not explicitly called."""
        user = CustomUser(email="   CUSTOMER@Example.COM   ")
        user.save()
        assert user.email == "customer@example.com"
        mock_super_save.assert_called_once()


class TestCustomUserManager:
    """Tests verifying CustomUserManager email normalization and creation behaviour."""

    def test_normalize_email_strips_and_lowercases(self):
        """Verify normalize_email lowercases both local and domain parts and strips whitespace."""
        manager = CustomUser.objects
        assert manager.normalize_email("  USER@DOMAIN.COM  ") == "user@domain.com"
        assert manager.normalize_email("Jane.Doe+Tag@SUB.DOMAIN.ORG") == "jane.doe+tag@sub.domain.org"
        assert manager.normalize_email("") == ""
        assert manager.normalize_email(None) == ""

    @patch.object(CustomUser, "save")
    def test_create_user_with_mixed_case_email(self, mock_save):
        """Verify creating a regular user normalizes mixed-case email to lowercase."""
        user = CustomUser.objects.create_user(
            email="   CUSTOMER@FineFit.STORE   ",
            password="SecurePassword123!",
            first_name="Jane",
            last_name="Doe",
        )

        mock_save.assert_called_once()
        # Enforce full lowercase normalization (both local-part and domain)
        assert user.email == "customer@finefit.store"
        assert user.check_password("SecurePassword123!") is True
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False
        assert isinstance(user.id, uuid.UUID)

    def test_create_user_without_email_raises_value_error(self):
        """Verify attempting to create a user without an email raises ValueError."""
        with pytest.raises(ValueError, match="The Email field must be set."):
            CustomUser.objects.create_user(email="", password="SomePassword123")

        with pytest.raises(ValueError, match="The Email field must be set."):
            CustomUser.objects.create_user(email=None, password="SomePassword123")

        with pytest.raises(ValueError, match="The Email field must be set."):
            CustomUser.objects.create_user(email="   ", password="SomePassword123")

    @patch.object(CustomUser, "save")
    def test_create_superuser_with_mixed_case_email(self, mock_save):
        """Verify creating a superuser normalizes mixed-case email and sets permissions."""
        superuser = CustomUser.objects.create_superuser(
            email="  ADMIN@FineFit.STORE  ",
            password="SuperAdminPassword123!",
        )

        mock_save.assert_called_once()
        assert superuser.email == "admin@finefit.store"
        assert superuser.check_password("SuperAdminPassword123!") is True
        assert superuser.is_staff is True
        assert superuser.is_superuser is True
        assert superuser.is_active is True
        assert isinstance(superuser.id, uuid.UUID)

    def test_create_superuser_invalid_is_staff_raises_value_error(self):
        """Verify creating a superuser with is_staff=False raises ValueError."""
        with pytest.raises(ValueError, match="Superuser must have is_staff=True."):
            CustomUser.objects.create_superuser(
                email="admin@finefit.store",
                password="Password123!",
                is_staff=False,
            )

    def test_create_superuser_invalid_is_superuser_raises_value_error(self):
        """Verify creating a superuser with is_superuser=False raises ValueError."""
        with pytest.raises(ValueError, match="Superuser must have is_superuser=True."):
            CustomUser.objects.create_superuser(
                email="admin@finefit.store",
                password="Password123!",
                is_superuser=False,
            )

    @patch.object(models.Manager, "get")
    def test_get_by_natural_key_case_insensitive(self, mock_get):
        """Verify get_by_natural_key performs case-insensitive lookup with trimmed email."""
        mock_user = MagicMock()
        mock_get.return_value = mock_user

        user = CustomUser.objects.get_by_natural_key("  MixedCase@FineFit.STORE  ")

        mock_get.assert_called_once_with(email__iexact="MixedCase@FineFit.STORE".strip())
        assert user == mock_user
