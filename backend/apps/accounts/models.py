import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


class CustomUser(AbstractUser):
    """
    Custom user model for FineFit E-Commerce platform.

    - Uses UUID as primary key to make IDs unguessable and prevent enumeration.
      Note: UUIDs do not replace authentication, authorization, or object-level isolation.
    - Uses unique, case-insensitive email address as primary authentication identifier.
    - Removes the legacy username field.
    - Relies on Django's built-in Groups and Permissions system for staff role-based access.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("Unique identifier for this user across the platform.")
    )
    username = None  # Explicitly removed
    email = models.EmailField(
        _("email address"),
        unique=True,
        error_messages={
            "unique": _("A user with that email already exists."),
        },
    )
    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        blank=True,
        null=True,
        help_text=_("Contact phone number for notifications and delivery verification.")
    )
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    account_verified = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="unique_case_insensitive_email",
                violation_error_message=_("A user with that email already exists."),
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class PasswordResetRequest(models.Model):
    """
    One-time password reset token.

    Created when a user requests a forgotten-password reset via email or phone.
    Single-use, time-limited, and bound to an identifier (email or phone).
    """

    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Password Reset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identifier = models.CharField(max_length=255, help_text="Email or phone number the reset was requested for.")
    token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=32, choices=Purpose.choices, default=Purpose.PASSWORD_RESET)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = _("password reset request")
        verbose_name_plural = _("password reset requests")
        ordering = ["-created_at"]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_used(self):
        return self.used_at is not None

    def mark_used(self):
        from django.utils import timezone
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return f"Reset for {self.identifier} ({self.token})"


class VerificationCode(models.Model):
    """
    One-time verification code (6-digit numeric).

    Used for account registration verification, sensitive-action re-verification,
    and 2FA challenges. Codes are hashed before storage.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        PASSWORD_RESET = "password_reset", "Password Reset"
        SENSITIVE_ACTION = "sensitive_action", "Sensitive Action"
        TWO_FACTOR = "two_factor", "Two Factor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="verification_codes",
        null=True,
        blank=True,
        help_text="User the code belongs to (null for pre-registration flows).",
    )
    identifier = models.CharField(max_length=255, help_text="Email or phone number the code was sent to.")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    code_hash = models.CharField(max_length=128, help_text="Hashed verification code.")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("verification code")
        verbose_name_plural = _("verification codes")
        ordering = ["-created_at"]

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def is_used(self):
        return self.used_at is not None

    def is_locked(self):
        return self.attempt_count >= 5

    def check_code(self, code):
        from django.utils import timezone
        from django.contrib.auth.hashers import check_password
        if self.is_used() or self.is_expired() or self.is_locked():
            return False
        self.attempt_count += 1
        self.save(update_fields=["attempt_count"])
        if check_password(code, self.code_hash):
            self.used_at = timezone.now()
            self.save(update_fields=["used_at"])
            return True
        return False

    def __str__(self):
        return f"Code for {self.identifier} ({self.channel})"


class TwoFactorMethod(models.Model):
    """
    A user's enrolled two-factor authentication method.

    Each user may enroll one or more methods (email or SMS). One can be primary.
    """

    class Method(models.TextChoices):
        EMAIL = "email", "Email OTP"
        SMS = "sms", "SMS OTP"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="two_factor_methods",
    )
    method = models.CharField(max_length=16, choices=Method.choices)
    destination = models.CharField(
        max_length=255,
        help_text="Masked destination (e.g. e***@f****.com or +1*******5678).",
    )
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("two factor method")
        verbose_name_plural = _("two factor methods")
        ordering = ["-is_primary", "-enrolled_at"]

    def __str__(self):
        return f"{self.user.email} - {self.method} ({self.destination})"


class BackupCode(models.Model):
    """
    Single-use backup code for 2FA lockout recovery.

    Generated when a user enrolls in 2FA. Each code can be used once.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="backup_codes",
    )
    code_hash = models.CharField(max_length=128, help_text="Hashed backup code.")
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("backup code")
        verbose_name_plural = _("backup codes")
        ordering = ["-created_at"]

    def is_used(self):
        return self.used_at is not None

    def check_code(self, code):
        from django.contrib.auth.hashers import check_password
        if self.is_used():
            return False
        if check_password(code, self.code_hash):
            from django.utils import timezone
            self.used_at = timezone.now()
            self.save(update_fields=["used_at"])
            return True
        return False

    def __str__(self):
        return f"Backup code for {self.user.email}"
