from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
import logging
from datetime import timedelta
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import (
    BackupCode,
    CustomUser,
    PasswordResetRequest,
    TwoFactorMethod,
    VerificationCode,
)
from .serializers import UserSerializer
from .utils import OTP_CODE_LENGTH, generate_otp, mask_email, mask_phone, send_otp_email, send_otp_sms, send_reset_email

logger = logging.getLogger(__name__)

SESSION_REMEMBER_AGE = 1209600  # 2 weeks in seconds
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = getattr(settings, "PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 1)
OTP_CODE_EXPIRY_MINUTES = getattr(settings, "OTP_CODE_EXPIRY_MINUTES", 10)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES = getattr(
    settings, "SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES", 30
)
VERIFICATION_MAX_PER_DAY = getattr(settings, "VERIFICATION_MAX_PER_DAY", 15)

# Device verification helpers
device_signer = TimestampSigner()
DEVICE_COOKIE_NAME = getattr(settings, "DEVICE_VERIFICATION_COOKIE_NAME", "ff_device_token")
DEVICE_COOKIE_DAYS = getattr(settings, "DEVICE_VERIFICATION_DAYS", 30)


def get_device_token(request):
    """Read and verify the device verification cookie."""
    token = request.COOKIES.get(DEVICE_COOKIE_NAME)
    if not token:
        return None
    try:
        data = device_signer.unsign(token, max_age=DEVICE_COOKIE_DAYS * 86400)
        return data  # "user_id:device_id"
    except (BadSignature, SignatureExpired):
        return None


def set_device_cookie(response, user_id, device_id):
    """Set a signed device verification cookie."""
    token = device_signer.sign(f"{user_id}:{device_id}")
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        token,
        max_age=DEVICE_COOKIE_DAYS * 86400,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    return token


def is_device_verified(request, user_id):
    """Check if the current device/browser is verified for this user."""
    token = get_device_token(request)
    if not token:
        return False
    try:
        stored_user_id, _ = token.split(":", 1)
        return stored_user_id == str(user_id)
    except ValueError:
        return False


def generate_device_id(request):
    """Generate a simple device identifier from request metadata."""
    ua = request.META.get("HTTP_USER_AGENT", "")
    ip = request.META.get("REMOTE_ADDR", "")
    import hashlib
    return hashlib.sha256(f"{ua}:{ip}".encode()).hexdigest()[:16]


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
        identifier = request.data.get("identifier") or request.data.get("email") or request.data.get("phone") or request.data.get("username")
        password = request.data.get("password")

        if not identifier or not password:
            return Response(
                {"detail": "Identifier and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        identifier_clean = str(identifier).strip()
        user = authenticate(request, identifier=identifier_clean, password=password)
        if user is None and "@" in identifier_clean:
            user = authenticate(request, email=identifier_clean.lower(), password=password)
        if user is None:
            user = authenticate(request, username=identifier_clean, password=password)
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


class AdminLoginView(View):
    """
    HTML login page for the admin panel.
    GET renders the login form; POST authenticates and starts a session.
    """

    template_name = "admin_panel/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(request.GET.get("next") or "/admin/custom-dashboard/")
        return render(request, self.template_name, {"next": request.GET.get("next", "")})

    def post(self, request):
        identifier = request.POST.get("identifier", "").strip()
        password = request.POST.get("password", "")
        remember_me = request.POST.get("remember_me") == "on"
        next_url = request.POST.get("next") or "/admin/custom-dashboard/"

        if not identifier or not password:
            messages.error(request, "Email and password are required.")
            return render(request, self.template_name, {"next": next_url})

        user = authenticate(request, identifier=identifier, password=password)
        if user is None:
            messages.error(request, "Invalid email or password.")
            return render(request, self.template_name, {"next": next_url})

        if not user.is_active:
            messages.error(request, "This account is inactive.")
            return render(request, self.template_name, {"next": next_url})

        login(request, user)

        if remember_me:
            request.session.set_expiry(SESSION_REMEMBER_AGE)
        else:
            request.session.set_expiry(0)

        device_id = generate_device_id(request)

        # If device is already verified, skip 2FA/verification and go to dashboard.
        if is_device_verified(request, user.id):
            messages.success(request, f"Welcome back, {user.get_short_name() or user.email}.")
            return redirect(next_url)

        # Device not verified — require 2FA if enrolled, else email/phone verification.
        if user.two_factor_methods.filter(is_verified=True).exists():
            request.session["pending_2fa_user_id"] = str(user.id)
            request.session["device_id"] = device_id
            request.session["next_after_verify"] = next_url
            messages.info(request, "Please complete two-factor authentication.")
            return redirect("admin_panel:2fa_challenge")

        # No 2FA — require email/phone verification for new device.
        request.session["pending_verify_user_id"] = str(user.id)
        request.session["device_id"] = device_id
        request.session["next_after_verify"] = next_url
        messages.info(request, "Please verify your identity for this new device.")
        return redirect("admin_panel:verify_account")


class AdminLogoutView(View):
    """
    HTML logout endpoint for the admin panel.
    """

    def get(self, request):
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("admin_panel:login")

    def post(self, request):
        return self.get(request)


# ---------------------------------------------------------------------------
# HTML views — Admin panel
# ---------------------------------------------------------------------------


class ForgotPasswordView(View):
    """Request a password reset via email or phone."""

    template_name = "admin_panel/forgot_password.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        identifier = request.POST.get("identifier", "").strip()
        channel = request.POST.get("channel", "email")

        if not identifier:
            messages.error(request, "Email or phone number is required.")
            return render(request, self.template_name, {"identifier": identifier})

        User = get_user_model()
        try:
            if channel == "email":
                user = User.objects.get(email__iexact=identifier)
            else:
                user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            # Do not reveal whether the account exists
            messages.success(
                request,
                "If an account exists for that identifier, a reset link has been sent.",
            )
            return render(
                request,
                self.template_name,
                {"identifier": identifier, "channel": channel},
            )

        # Rate limit: max 3 reset requests per hour per identifier
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = PasswordResetRequest.objects.filter(
            identifier=identifier, created_at__gte=one_hour_ago
        ).count()
        if recent_count >= 3:
            messages.error(
                request,
                "Too many reset requests. Please try again later.",
            )
            return render(
                request,
                self.template_name,
                {"identifier": identifier, "channel": channel},
            )

        # Invalidate any previous unused tokens for this identifier
        PasswordResetRequest.objects.filter(
            identifier=identifier, used_at__isnull=True
        ).update(used_at=timezone.now())

        token_request = PasswordResetRequest.objects.create(
            identifier=identifier,
            expires_at=timezone.now()
            + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRY_HOURS),
            ip_address=self._get_client_ip(request),
        )

        reset_url = request.build_absolute_uri(
            f"/admin/reset-password/{token_request.token}/"
        )

        if channel == "email":
            send_reset_email(identifier, reset_url)
        else:
            send_otp_sms(identifier, str(token_request.token), "password_reset")

        messages.success(
            request,
            "If an account exists for that identifier, a reset link has been sent.",
        )
        return render(request, self.template_name, {"identifier": identifier})

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class ResetPasswordView(View):
    """Set a new password using a valid reset token."""

    template_name = "admin_panel/reset_password.html"

    def get(self, request, token):
        try:
            reset_request = PasswordResetRequest.objects.get(token=token)
        except PasswordResetRequest.DoesNotExist:
            messages.error(request, "Invalid or expired reset link.")
            return redirect("admin_panel:login")

        if reset_request.is_used() or reset_request.is_expired():
            messages.error(request, "This reset link is invalid or has expired.")
            return redirect("admin_panel:login")

        return render(request, self.template_name, {"token": token})

    def post(self, request, token):
        try:
            reset_request = PasswordResetRequest.objects.get(token=token)
        except PasswordResetRequest.DoesNotExist:
            messages.error(request, "Invalid or expired reset link.")
            return redirect("admin_panel:login")

        if reset_request.is_used() or reset_request.is_expired():
            messages.error(request, "This reset link is invalid or has expired.")
            return redirect("admin_panel:login")

        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, self.template_name, {"token": token})

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, self.template_name, {"token": token})

        User = get_user_model()
        try:
            if "@" in reset_request.identifier:
                user = User.objects.get(email__iexact=reset_request.identifier)
            else:
                user = User.objects.get(phone_number=reset_request.identifier)
        except User.DoesNotExist:
            messages.error(request, "Account not found.")
            return redirect("admin_panel:login")

        user.set_password(password)
        user.save()
        reset_request.mark_used()

        messages.success(request, "Your password has been reset successfully.")
        return redirect("admin_panel:login")


class VerifyAccountView(View):
    """
    Secure two-step account verification tied to the current user.

    Step 1: Select verification method (email/phone) → OTP sent to user's own
            contact (masked display, no manual entry).
    Step 2: Enter the 6-digit OTP → verify and complete.

    The identifier is never user-supplied — it always comes from request.user,
    preventing account takeover via entering another person's email/phone.
    """

    template_name = "admin_panel/verify_code.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to verify your account.")
            return redirect("admin_panel:login")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        purpose = request.GET.get("purpose", "registration")
        step = request.session.get("verify_step", "method")

        # Build masked destination options for the current user
        email_dest = mask_email(request.user.email) if request.user.email else None
        phone_dest = mask_phone(request.user.phone_number) if request.user.phone_number else None

        available_methods = []
        if request.user.email:
            available_methods.append(("email", email_dest, "Email"))
        if request.user.phone_number:
            available_methods.append(("sms", phone_dest, "SMS"))

        # If already on OTP step, show OTP entry form
        if step == "otp":
            return render(request, self.template_name, {
                "purpose": purpose,
                "step": "otp",
                "identifier": request.session.get("verify_identifier", ""),
                "channel": request.session.get("verify_channel", "email"),
                "available_methods": available_methods,
            })

        # Step 1: method selection form
        return render(request, self.template_name, {
            "purpose": purpose,
            "step": "method",
            "available_methods": available_methods,
            "email_dest": email_dest,
            "phone_dest": phone_dest,
        })

    def post(self, request):
        action = request.POST.get("action", "verify")
        purpose = request.POST.get("purpose", "registration")
        channel = request.POST.get("channel", "email")
        code = request.POST.get("code", "").strip()

        # Determine the actual identifier from the current user (never user-supplied)
        if channel == "email":
            identifier = request.user.email
        else:
            identifier = request.user.phone_number

        if not identifier:
            messages.error(request, f"No {channel} address found on your account.")
            return redirect("admin_panel:verify_account")

        # --- Step 1: Send OTP ---
        if action == "send_otp":
            if channel not in ("email", "sms"):
                messages.error(request, "Invalid verification method.")
                return redirect("admin_panel:verify_account")

            # Daily rate limit: max 15 OTP requests per user per day
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = VerificationCode.objects.filter(
                identifier=identifier,
                channel=channel,
                purpose=purpose,
                created_at__gte=today_start,
            ).count()
            if today_count >= VERIFICATION_MAX_PER_DAY:
                messages.error(
                    request,
                    f"Maximum {VERIFICATION_MAX_PER_DAY} verification requests per day reached. Try again tomorrow.",
                )
                return redirect("admin_panel:verify_account")

            # Invalidate any previous unused codes for this identifier/channel/purpose
            VerificationCode.objects.filter(
                identifier=identifier,
                channel=channel,
                purpose=purpose,
                used_at__isnull=True,
            ).update(used_at=timezone.now())

            # Create new verification code (bind to user)
            otp_code = generate_otp()
            verification_code = VerificationCode.objects.create(
                user=request.user,
                identifier=identifier,
                channel=channel,
                code_hash=make_password(otp_code),
                purpose=purpose,
                expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
            )

            # Send OTP
            sent = False
            if channel == "email":
                sent = send_otp_email(identifier, otp_code, purpose)
            else:
                sent = send_otp_sms(identifier, otp_code, purpose)

            if not sent:
                messages.error(request, "Failed to send verification code. Please try again.")
                return redirect("admin_panel:verify_account")

            # Store state for step 2
            request.session["verify_identifier"] = identifier
            request.session["verify_channel"] = channel
            request.session["verify_purpose"] = purpose
            request.session["verify_step"] = "otp"

            masked = mask_email(identifier) if channel == "email" else mask_phone(identifier)
            messages.success(
                request,
                f"A {OTP_CODE_LENGTH}-digit code has been sent to {masked}.",
            )
            return redirect("admin_panel:verify_account")

        # --- Step 2: Verify OTP ---
        elif action == "verify_otp":
            if not code:
                messages.error(request, "Verification code is required.")
                return redirect("admin_panel:verify_account")

            stored_identifier = request.session.get("verify_identifier", "")
            stored_channel = request.session.get("verify_channel", "email")
            stored_purpose = request.session.get("verify_purpose", "registration")

            if not stored_identifier:
                messages.error(request, "Verification session expired. Please start again.")
                return redirect("admin_panel:verify_account")

            try:
                verification_code = VerificationCode.objects.filter(
                    identifier=stored_identifier,
                    channel=stored_channel,
                    purpose=stored_purpose,
                    used_at__isnull=True,
                ).latest("created_at")
            except VerificationCode.DoesNotExist:
                messages.error(request, "No verification code found. Please request a new one.")
                return redirect("admin_panel:verify_account")

            if not verification_code.check_code(code):
                messages.error(request, "Invalid or expired code.")
                return redirect("admin_panel:verify_account")

            # Code verified successfully
            if stored_purpose == "registration":
                request.user.is_active = True
                request.user.save(update_fields=["is_active"])
                messages.success(
                    request, "Your account has been verified and activated."
                )
            else:
                messages.success(request, "Verification successful.")

            # Track per-channel verification
            if stored_channel == "email":
                request.user.email_verified = True
            elif stored_channel == "sms" or stored_channel == "phone":
                request.user.phone_verified = True
            # Update account verified if both verified (or relevant ones)
            if request.user.email_verified and request.user.phone_verified:
                request.user.account_verified = True
            elif request.user.email_verified and not request.user.phone_number:
                request.user.account_verified = True
            elif request.user.phone_verified and not request.user.email:
                request.user.account_verified = True
            else:
                # If only one exists, consider based on what's present
                if request.user.email_verified or request.user.phone_verified:
                    # If both fields exist and both verified -> true
                    if (not request.user.email or request.user.email_verified) and (not request.user.phone_number or request.user.phone_verified):
                        request.user.account_verified = True
            request.user.save(update_fields=["email_verified", "phone_verified", "account_verified"])

            request.session["last_verified_at"] = timezone.now().isoformat()

            # Mark device verified and redirect to dashboard
            device_id = request.session.get("device_id")
            next_url = request.session.get("next_after_verify", "/admin/custom-dashboard/")

            # Clear verification session state
            for key in ("verify_identifier", "verify_channel", "verify_purpose", "verify_step",
                        "device_id", "next_after_verify", "pending_verify_user_id"):
                request.session.pop(key, None)

            response = redirect(next_url)
            if device_id:
                set_device_cookie(response, request.user.id, device_id)

            return response

        # --- Resend OTP ---
        elif action == "resend_otp":
            stored_identifier = request.session.get("verify_identifier", "")
            stored_channel = request.session.get("verify_channel", "email")
            stored_purpose = request.session.get("verify_purpose", "registration")

            if not stored_identifier:
                messages.error(request, "Verification session expired. Please start again.")
                return redirect("admin_panel:verify_account")

            # Daily rate limit check
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = VerificationCode.objects.filter(
                identifier=stored_identifier,
                channel=stored_channel,
                purpose=stored_purpose,
                created_at__gte=today_start,
            ).count()
            if today_count >= VERIFICATION_MAX_PER_DAY:
                messages.error(
                    request,
                    f"Maximum {VERIFICATION_MAX_PER_DAY} verification requests per day reached.",
                )
                return redirect("admin_panel:verify_account")

            # Invalidate previous unused code
            VerificationCode.objects.filter(
                identifier=stored_identifier,
                channel=stored_channel,
                purpose=stored_purpose,
                used_at__isnull=True,
            ).update(used_at=timezone.now())

            # Send new OTP
            otp_code = generate_otp()
            VerificationCode.objects.create(
                user=request.user,
                identifier=stored_identifier,
                channel=stored_channel,
                code_hash=make_password(otp_code),
                purpose=stored_purpose,
                expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
            )

            sent = False
            if stored_channel == "email":
                sent = send_otp_email(stored_identifier, otp_code, stored_purpose)
            else:
                sent = send_otp_sms(stored_identifier, otp_code, stored_purpose)

            if not sent:
                messages.error(request, "Failed to resend verification code.")
            else:
                masked = mask_email(stored_identifier) if stored_channel == "email" else mask_phone(stored_identifier)
                messages.success(
                    request,
                    f"A new {OTP_CODE_LENGTH}-digit code has been sent to {masked}.",
                )

            return redirect("admin_panel:verify_account")

        # Unknown action
        messages.error(request, "Invalid action.")
        return redirect("admin_panel:verify_account")


# ---------------------------------------------------------------------------
# HTML views — Two-factor authentication
# ---------------------------------------------------------------------------


class TwoFactorEnrollView(View):
    """Enroll a 2FA method (email or SMS)."""

    template_name = "admin_panel/2fa_enroll.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        existing = request.user.two_factor_methods.filter(is_verified=True)
        return render(
            request,
            self.template_name,
            {"existing_methods": existing},
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")

        method = request.POST.get("method", "")
        destination = request.POST.get("destination", "").strip()

        if method not in dict(TwoFactorMethod.Method.choices):
            messages.error(request, "Invalid method selected.")
            return render(request, self.template_name)

        # Validate destination matches user's email or phone
        if method == TwoFactorMethod.Method.EMAIL:
            if destination.lower() != request.user.email.lower():
                messages.error(request, "Email does not match your account.")
                return render(request, self.template_name)
            destination_display = mask_email(destination)
        else:
            if destination != request.user.phone_number:
                messages.error(request, "Phone number does not match your account.")
                return render(request, self.template_name)
            destination_display = mask_phone(destination)

        # Prevent duplicate method type
        if request.user.two_factor_methods.filter(method=method).exists():
            messages.error(request, "This method has already been added.")
            return render(request, self.template_name)

        # Create unverified method
        tf_method = TwoFactorMethod.objects.create(
            user=request.user,
            method=method,
            destination=destination_display,
            is_verified=False,
            is_primary=not request.user.two_factor_methods.exists(),
        )

        # Send OTP to verify
        code = generate_otp()
        VerificationCode.objects.create(
            user=request.user,
            identifier=destination,
            channel=method,
            code_hash=make_password(code),
            purpose=VerificationCode.Purpose.TWO_FACTOR,
            expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
        )

        if method == TwoFactorMethod.Method.EMAIL:
            send_otp_email(destination, code, "two-factor enrollment")
        else:
            send_otp_sms(destination, code, "two-factor enrollment")

        request.session["pending_2fa_enroll_id"] = str(tf_method.id)
        messages.info(request, f"A verification code has been sent to {destination_display}.")
        return redirect("admin_panel:2fa_enroll")


class TwoFactorChallengeView(View):
    """OTP challenge during login for users with enrolled 2FA."""

    template_name = "admin_panel/2fa_challenge.html"

    def get(self, request):
        pending_user_id = request.session.get("pending_2fa_user_id")
        if not pending_user_id:
            return redirect("admin_panel:login")
        return render(request, self.template_name)

    def post(self, request):
        pending_user_id = request.session.get("pending_2fa_user_id")
        code = request.POST.get("code", "").strip()
        use_backup = request.POST.get("use_backup_code") == "on"
        backup_code = request.POST.get("backup_code", "").strip()

        if not pending_user_id:
            return redirect("admin_panel:login")

        User = get_user_model()
        try:
            user = User.objects.get(id=pending_user_id)
        except User.DoesNotExist:
            return redirect("admin_panel:login")

        verified = False

        if use_backup and backup_code:
            try:
                bc = BackupCode.objects.filter(user=user, used_at__isnull=True).first()
                if bc and bc.check_code(backup_code):
                    verified = True
            except BackupCode.DoesNotExist:
                pass
        else:
            # Verify against the latest unverified 2FA code
            try:
                vc = VerificationCode.objects.filter(
                    user=user,
                    purpose=VerificationCode.Purpose.TWO_FACTOR,
                    used_at__isnull=True,
                ).latest("created_at")
                if vc.check_code(code):
                    verified = True
            except VerificationCode.DoesNotExist:
                pass

        if not verified:
            messages.error(request, "Invalid code.")
            return render(request, self.template_name)

        # 2FA succeeded — complete login and mark device verified.
        del request.session["pending_2fa_user_id"]
        device_id = request.session.get("device_id")
        next_url = request.session.get("next_after_verify", "/admin/custom-dashboard/")
        login(request, user)

        response = redirect(next_url)
        if device_id:
            set_device_cookie(response, user.id, device_id)
        # Clear verify session state
        for key in ("device_id", "next_after_verify", "pending_verify_user_id"):
            request.session.pop(key, None)

        messages.success(
            request, f"Welcome back, {user.get_short_name() or user.email}."
        )
        return response


class TwoFactorSettingsView(View):
    """Manage 2FA methods and backup codes."""

    template_name = "admin_panel/2fa_settings.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")
        methods = request.user.two_factor_methods.all()
        backup_codes = request.user.backup_codes.filter(used_at__isnull=True)
        return render(
            request,
            self.template_name,
            {"methods": methods, "backup_codes": backup_codes},
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("admin_panel:login")

        action = request.POST.get("action", "")

        if action == "add_method":
            method = request.POST.get("method", "")
            destination = request.POST.get("destination", "").strip()
            # Same validation as enroll
            if method not in dict(TwoFactorMethod.Method.choices):
                messages.error(request, "Invalid method.")
                return redirect("admin_panel:2fa_settings")
            if method == TwoFactorMethod.Method.EMAIL:
                if destination.lower() != request.user.email.lower():
                    messages.error(request, "Email does not match your account.")
                    return redirect("admin_panel:2fa_settings")
            else:
                if destination != request.user.phone_number:
                    messages.error(request, "Phone does not match your account.")
                    return redirect("admin_panel:2fa_settings")

            if request.user.two_factor_methods.filter(method=method).exists():
                messages.error(request, "This method has already been added.")
                return redirect("admin_panel:2fa_settings")

            tf_method = TwoFactorMethod.objects.create(
                user=request.user,
                method=method,
                destination=mask_email(destination)
                if method == TwoFactorMethod.Method.EMAIL
                else mask_phone(destination),
                is_verified=False,
                is_primary=not request.user.two_factor_methods.filter(
                    is_verified=True
                ).exists(),
            )
            code = generate_otp()
            VerificationCode.objects.create(
                user=request.user,
                identifier=destination,
                channel=method,
                code_hash=make_password(code),
                purpose=VerificationCode.Purpose.TWO_FACTOR,
                expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
            )
            if method == TwoFactorMethod.Method.EMAIL:
                send_otp_email(destination, code, "two-factor enrollment")
            else:
                send_otp_sms(destination, code, "two-factor enrollment")
            request.session["pending_2fa_enroll_id"] = str(tf_method.id)
            messages.info(
                request, "Verify the code sent to complete enrollment."
            )
            return redirect("admin_panel:2fa_challenge")

        elif action == "remove_method":
            method_id = request.POST.get("method_id", "")
            try:
                method = TwoFactorMethod.objects.get(
                    id=method_id, user=request.user
                )
                method.delete()
                messages.success(request, "2FA method removed.")
            except TwoFactorMethod.DoesNotError:  # noqa: F821
                messages.error(request, "Method not found.")
            return redirect("admin_panel:2fa_settings")

        elif action == "generate_backup_codes":
            request.user.backup_codes.filter(used_at__isnull=True).delete()
            codes = []
            for _ in range(8):
                code = generate_otp(length=8)
                BackupCode.objects.create(
                    user=request.user, code_hash=make_password(code)
                )
                codes.append(code)
            # Show codes once in template context via session
            request.session["new_backup_codes"] = codes
            messages.success(
                request, "New backup codes generated. Save them somewhere safe."
            )
            return redirect("admin_panel:2fa_settings")

        return redirect("admin_panel:2fa_settings")


# ---------------------------------------------------------------------------
# API views — /api/v1/auth/
# ---------------------------------------------------------------------------


class ApiForgotPasswordView(APIView):
    """Request a password reset via email or phone (API)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("identifier", "").strip()
        channel = request.data.get("channel", "email")

        if not identifier:
            return Response(
                {"detail": "Identifier is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()
        try:
            if channel == "email":
                user = User.objects.get(email__iexact=identifier)
            else:
                user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            # Do not reveal whether the account exists
            return Response(
                {
                    "detail": "If an account exists for that identifier, a reset link has been sent."
                },
                status=status.HTTP_200_OK,
            )

        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = PasswordResetRequest.objects.filter(
            identifier=identifier, created_at__gte=one_hour_ago
        ).count()
        if recent_count >= 3:
            return Response(
                {"detail": "Too many reset requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        PasswordResetRequest.objects.filter(
            identifier=identifier, used_at__isnull=True
        ).update(used_at=timezone.now())

        token_request = PasswordResetRequest.objects.create(
            identifier=identifier,
            expires_at=timezone.now()
            + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRY_HOURS),
            ip_address=self._get_client_ip(request),
        )

        reset_url = request.build_absolute_uri(
            f"/api/v1/auth/reset-password/?token={token_request.token}"
        )

        if channel == "email":
            send_reset_email(identifier, reset_url)
        else:
            send_otp_sms(identifier, str(token_request.token), "password_reset")

        return Response(
            {
                "detail": "If an account exists for that identifier, a reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class ApiResetPasswordView(APIView):
    """Reset password using a valid token (API)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("token", "")
        password = request.data.get("password", "")

        if not token or not password:
            return Response(
                {"detail": "Token and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reset_request = PasswordResetRequest.objects.get(token=token)
        except PasswordResetRequest.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired reset token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reset_request.is_used() or reset_request.is_expired():
            return Response(
                {"detail": "This reset token is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()
        try:
            if "@" in reset_request.identifier:
                user = User.objects.get(email__iexact=reset_request.identifier)
            else:
                user = User.objects.get(phone_number=reset_request.identifier)
        except User.DoesNotExist:
            return Response(
                {"detail": "Account not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()
        reset_request.mark_used()

        return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)


class ApiVerifyView(APIView):
    """
    Secure two-step account verification (API).

    Action "send_otp":   channel -> send OTP to authenticated user's contact
    Action "verify_otp": code     -> verify code
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        action = request.data.get("action", "verify_otp")
        channel = request.data.get("channel", "email")
        code = request.data.get("code", "").strip()
        purpose = request.data.get("purpose", "registration")

        # Determine the actual identifier from the current user (never user-supplied)
        if channel == "email":
            identifier = request.user.email
        else:
            identifier = request.user.phone_number

        if not identifier:
            return Response(
                {"detail": f"No {channel} address found on your account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Step 1: Send OTP ---
        if action == "send_otp":
            if channel not in ("email", "sms"):
                return Response(
                    {"detail": "Invalid channel. Use 'email' or 'sms'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Daily rate limit
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = VerificationCode.objects.filter(
                identifier=identifier,
                channel=channel,
                purpose=purpose,
                created_at__gte=today_start,
            ).count()
            if today_count >= VERIFICATION_MAX_PER_DAY:
                return Response(
                    {
                        "detail": f"Maximum {VERIFICATION_MAX_PER_DAY} verification requests per day reached."
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Invalidate previous unused codes
            VerificationCode.objects.filter(
                identifier=identifier,
                channel=channel,
                purpose=purpose,
                used_at__isnull=True,
            ).update(used_at=timezone.now())

            # Create and send OTP (bind to user)
            otp_code = generate_otp()
            VerificationCode.objects.create(
                user=request.user,
                identifier=identifier,
                channel=channel,
                code_hash=make_password(otp_code),
                purpose=purpose,
                expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
            )

            sent = False
            if channel == "email":
                sent = send_otp_email(identifier, otp_code, purpose)
            else:
                sent = send_otp_sms(identifier, otp_code, purpose)

            if not sent:
                return Response(
                    {"detail": "Failed to send verification code."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            masked = mask_email(identifier) if channel == "email" else mask_phone(identifier)
            return Response(
                {
                    "detail": f"A {OTP_CODE_LENGTH}-digit code has been sent to {masked}.",
                    "channel": channel,
                },
                status=status.HTTP_200_OK,
            )

        # --- Step 2: Verify OTP ---
        elif action == "verify_otp":
            if not code:
                return Response(
                    {"detail": "Verification code is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stored_identifier = request.session.get("verify_identifier", "")
            stored_channel = request.session.get("verify_channel", "email")
            stored_purpose = request.session.get("verify_purpose", "registration")

            if not stored_identifier:
                return Response(
                    {"detail": "Verification session expired. Please start again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                verification_code = VerificationCode.objects.filter(
                    identifier=stored_identifier,
                    channel=stored_channel,
                    purpose=stored_purpose,
                    used_at__isnull=True,
                ).latest("created_at")
            except VerificationCode.DoesNotExist:
                return Response(
                    {"detail": "No verification code found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not verification_code.check_code(code):
                return Response(
                    {"detail": "Invalid or expired code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if stored_purpose == "registration":
                request.user.is_active = True
                request.user.save(update_fields=["is_active"])

            # Track per-channel verification for API flow (use session or infer)
            stored_channel = request.session.get("verify_channel") or channel
            if stored_channel == "email":
                request.user.email_verified = True
            elif stored_channel == "sms":
                request.user.phone_verified = True
            if request.user.email_verified and request.user.phone_verified:
                request.user.account_verified = True
            elif request.user.email_verified and not request.user.phone_number:
                request.user.account_verified = True
            elif request.user.phone_verified and not request.user.email:
                request.user.account_verified = True
            request.user.save(update_fields=["email_verified", "phone_verified", "account_verified"])

            return Response({"detail": "Verification successful."}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid action. Use 'send_otp' or 'verify_otp'."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class Api2FAEnrollView(APIView):
    """Enroll a 2FA method (API)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        method = request.data.get("method", "")
        destination = request.data.get("destination", "").strip()

        if method not in dict(TwoFactorMethod.Method.choices):
            return Response(
                {"detail": "Invalid method."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if method == TwoFactorMethod.Method.EMAIL:
            if destination.lower() != request.user.email.lower():
                return Response(
                    {"detail": "Email does not match your account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if destination != request.user.phone_number:
                return Response(
                    {"detail": "Phone does not match your account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if request.user.two_factor_methods.filter(method=method).exists():
            return Response(
                {"detail": "This method has already been added."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        TwoFactorMethod.objects.filter(user=request.user, is_primary=True).update(
            is_primary=False
        )
        tf_method = TwoFactorMethod.objects.create(
            user=request.user,
            method=method,
            destination=mask_email(destination)
            if method == TwoFactorMethod.Method.EMAIL
            else mask_phone(destination),
            is_verified=False,
            is_primary=True,
        )
        code = generate_otp()
        VerificationCode.objects.create(
            user=request.user,
            identifier=destination,
            channel=method,
            code_hash=make_password(code),
            purpose=VerificationCode.Purpose.TWO_FACTOR,
            expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
        )
        if method == TwoFactorMethod.Method.EMAIL:
            send_otp_email(destination, code, "two-factor enrollment")
        else:
            send_otp_sms(destination, code, "two-factor enrollment")

        return Response(
            {
                "detail": "Verification code sent. Confirm to complete enrollment.",
                "method_id": str(tf_method.id),
            },
            status=status.HTTP_200_OK,
        )


class Api2FAChallengeView(APIView):
    """Request a 2FA OTP challenge (API)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        methods = request.user.two_factor_methods.filter(is_verified=True)
        if not methods.exists():
            return Response(
                {"detail": "No verified 2FA method enrolled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        method = methods.first()
        code = generate_otp()
        VerificationCode.objects.create(
            user=request.user,
            identifier=method.destination,
            channel=method.method,
            code_hash=make_password(code),
            purpose=VerificationCode.Purpose.TWO_FACTOR,
            expires_at=timezone.now() + timedelta(minutes=OTP_CODE_EXPIRY_MINUTES),
        )
        if method.method == TwoFactorMethod.Method.EMAIL:
            send_otp_email(method.destination, code, "two-factor challenge")
        else:
            send_otp_sms(method.destination, code, "two-factor challenge")

        return Response(
            {"detail": f"Code sent to {method.destination}."},
            status=status.HTTP_200_OK,
        )


class Api2FAVerifyView(APIView):
    """Verify a 2FA OTP code and return JWT tokens (API)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("identifier", "").strip()
        code = request.data.get("code", "").strip()
        use_backup = request.data.get("use_backup_code", False)
        backup_code = request.data.get("backup_code", "").strip()

        if not identifier:
            return Response(
                {"detail": "Identifier is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        User = get_user_model()
        try:
            if "@" in identifier:
                user = User.objects.get(email__iexact=identifier)
            else:
                user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        verified = False

        if use_backup and backup_code:
            try:
                bc = BackupCode.objects.filter(user=user, used_at__isnull=True).first()
                if bc and bc.check_code(backup_code):
                    verified = True
            except BackupCode.DoesNotExist:
                pass
        else:
            try:
                vc = VerificationCode.objects.filter(
                    user=user,
                    purpose=VerificationCode.Purpose.TWO_FACTOR,
                    used_at__isnull=True,
                ).latest("created_at")
                if vc.check_code(code):
                    verified = True
            except VerificationCode.DoesNotExist:
                pass

        if not verified:
            return Response(
                {"detail": "Invalid code."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generate JWT tokens
        refresh = TokenObtainPairView.get_token(user)
        access_token = refresh.access_token

        return Response(
            {
                "detail": "2FA verification successful.",
                "access": str(access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class Api2FASettingsView(APIView):
    """Manage 2FA methods and backup codes (API)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        methods = []
        for m in request.user.two_factor_methods.all():
            methods.append(
                {
                    "id": str(m.id),
                    "method": m.method,
                    "destination": m.destination,
                    "is_primary": m.is_primary,
                    "is_verified": m.is_verified,
                }
            )
        backup_codes_count = request.user.backup_codes.filter(
            used_at__isnull=True
        ).count()
        return Response(
            {
                "methods": methods,
                "backup_codes_remaining": backup_codes_count,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        action = request.data.get("action", "")

        if action == "generate_backup_codes":
            request.user.backup_codes.filter(used_at__isnull=True).delete()
            codes = []
            for _ in range(8):
                code = generate_otp(length=8)
                BackupCode.objects.create(user=request.user, code_hash=make_password(code))
                codes.append(code)
            return Response(
                {
                    "detail": "New backup codes generated.",
                    "backup_codes": codes,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"detail": "Invalid action."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request):
        method_id = request.data.get("method_id", "")
        try:
            method = TwoFactorMethod.objects.get(id=method_id, user=request.user)
            method.delete()
            return Response(
                {"detail": "2FA method removed."},
                status=status.HTTP_200_OK,
            )
        except TwoFactorMethod.DoesNotExist:
            return Response(
                {"detail": "Method not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


# ---------------------------------------------------------------------------
# API views — JWT token blacklist
# ---------------------------------------------------------------------------


class ApiTokenBlacklistView(APIView):
    """Blacklist a refresh token on logout (API)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh", "")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from rest_framework_simplejwt.tokens import RefreshToken

            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Token blacklisted."}, status=status.HTTP_200_OK)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"detail": "Invalid or already blacklisted token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ---------------------------------------------------------------------------
# JWT token obtain/refresh wrappers (to match URL naming)
# ---------------------------------------------------------------------------


class ApiTokenObtainPairView(TokenObtainPairView):
    """Obtain JWT access/refresh tokens (email + password)."""

    permission_classes = [permissions.AllowAny]


class ApiTokenRefreshView(TokenRefreshView):
    """Refresh JWT access token."""

    permission_classes = [permissions.AllowAny]
