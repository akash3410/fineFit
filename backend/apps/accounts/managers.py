from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Custom manager for CustomUser where email is the unique identifier
    for authentication instead of a username.
    Enforces stripped, lowercase normalization for case-insensitive email identity.
    """

    @classmethod
    def normalize_email(cls, email):
        """
        Normalize email address by stripping whitespace and converting to lowercase.
        """
        if not email:
            return ""
        return email.strip().lower()

    def get_by_natural_key(self, email):
        """
        Retrieve user by email using case-insensitive lookup.
        """
        if not email:
            return self.get(**{self.model.USERNAME_FIELD: email})
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": email.strip()})

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user with a normalized email and password.
        """
        email = self.normalize_email(email)
        if not email:
            raise ValueError(_("The Email field must be set."))

        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with all permissions.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)
