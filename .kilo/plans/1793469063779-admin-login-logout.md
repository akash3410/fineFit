# Plan: Forgot Password, Email/Phone Verification, Two-Factor Authentication

## Goal
Add secure, fully functional account recovery, verification, and two-factor authentication to FineFit. Covers:
- Forgot password via email or phone
- Email/phone verification enforced at registration and sensitive actions
- Two-factor authentication (Email OTP + SMS OTP) mandatory for all users
- Session auth for HTML admin panel + JWT access/refresh tokens for API clients

## Current State
- Auth is session-based (Django `sessionid` cookie) for HTML admin panel and DRF API (`SessionAuthentication`)
- HTML login/logout at `/admin/login/`, `/admin/logout/` (recently implemented)
- DRF API login/logout at `/api/v1/login/`, `/api/v1/logout/` (JSON-only)
- `CustomUser`: email (USERNAME_FIELD, unique), phone_number (optional), `EmailOrPhoneBackend` authenticates by email or phone
- No `djangorestframework-simplejwt` installed
- No EMAIL_BACKEND configured (Django defaults to console backend)
- No password reset, verification, or 2FA models/views exist
- `EmailOrPhoneBackend` allows login with unverified accounts

## Confirmed Design Decisions (from user)
1. **Auth architecture**: Session for HTML admin panel + JWT access/refresh for `/api/v1/` API clients
2. **Forgot password channels**: Email AND phone (not email-only)
3. **SMS provider**: Mock/dev-only — log OTP to console in dev; no real SMS gateway
4. **Verification scope**: Enforced at registration (account inactive until verified) AND sensitive actions (change email/phone/password, delete account, change role)
5. **2FA methods**: Email OTP + SMS OTP (not TOTP)
6. **2FA enforcement**: Mandatory for ALL users — no access without enrolled 2FA

## New Models (`backend/apps/accounts/models.py`)
| Model | Fields | Purpose |
|-------|--------|---------|
| `PasswordResetRequest` | id (UUID), email/phone, token (UUID, unique), purpose, expires_at, used_at, created_at, ip_address | One-time password reset tokens |
| `VerificationCode` | id (UUID), user, channel (email/sms), code (6-digit), purpose (registration/password_reset/sensitive_action/2fa), expires_at, used_at, attempt_count, created_at | OTP codes for verification & 2FA |
| `TwoFactorMethod` | id (UUID), user, method (email/sms), destination (masked email/phone), is_primary, is_verified, enrolled_at, updated_at | User's enrolled 2FA method(s) |
| `BackupCode` | id (UUID), user, code (8-char), used_at, created_at | Single-use backup codes for 2FA lockout recovery |

### Key model behaviors
- `VerificationCode.code`: 6-digit numeric, 10-min expiry, max 5 attempts before lockout
- `PasswordResetRequest.token`: UUID v4, 1-hour expiry, single-use
- `TwoFactorMethod.destination`: masked (e.g., `e***@f****.com`, `+1*******5678`)
- All codes hashed before storage (like passwords) — never store plaintext codes

## New Views — HTML (`backend/apps/accounts/views.py`)
| View | URL | Methods | Purpose |
|------|-----|---------|---------|
| `ForgotPasswordView` | `/admin/forgot-password/` | GET/POST | Request reset via email or phone |
| `ResetPasswordView` | `/admin/reset-password/<uuid:token>/` | GET/POST | Set new password with valid token |
| `VerifyAccountView` | `/admin/verify/` | GET/POST | Enter verification code (registration/sensitive action) |
| `TwoFactorEnrollView` | `/admin/2fa/enroll/` | GET/POST | Choose + verify 2FA method (email/sms) |
| `TwoFactorChallengeView` | `/admin/2fa/challenge/` | GET/POST | OTP challenge during login |
| `TwoFactorSettingsView` | `/admin/2fa/settings/` | GET/POST | Manage 2FA methods, backup codes |

## New Views — API (`backend/apps/accounts/views.py`)
| View | URL | Methods | Purpose |
|------|-----|---------|---------|
| `ApiForgotPasswordView` | `/api/v1/auth/forgot-password/` | POST | Request reset (email/phone) |
| `ApiResetPasswordView` | `/api/v1/auth/reset-password/` | POST | Confirm reset with token + new password |
| `ApiVerifyView` | `/api/v1/auth/verify/` | POST | Submit verification code |
| `Api2FAEnrollView` | `/api/v1/auth/2fa/enroll/` | POST | Enroll 2FA method |
| `Api2FAChallengeView` | `/api/v1/auth/2fa/challenge/` | POST | Request OTP challenge |
| `Api2FAVerifyView` | `/api/v1/auth/2fa/verify/` | POST | Verify OTP code, return JWT tokens |
| `Api2FASettingsView` | `/api/v1/auth/2fa/settings/` | GET/POST/DELETE | Manage methods + backup codes |

## JWT Views (API)
Use `djangorestframework-simplejwt`:
- `TokenObtainPairView` → `/api/v1/auth/token/` (email + password → access + refresh)
- `TokenRefreshView` → `/api/v1/auth/token/refresh/` (refresh → new access)
- `TokenBlacklistView` → `/api/v1/auth/token/blacklist/` (refresh → blacklist on logout)

## URL Routes
### `backend/apps/admin_panel/urls.py`
```
path("forgot-password/", ..., name="forgot_password")
path("reset-password/<uuid:token>/", ..., name="reset_password")
path("verify/", ..., name="verify_account")
path("2fa/enroll/", ..., name="2fa_enroll")
path("2fa/challenge/", ..., name="2fa_challenge")
path("2fa/settings/", ..., name="2fa_settings")
```

### `backend/apps/accounts/urls.py`
```
path("forgot-password/", ApiForgotPasswordView.as_view(), name="api-forgot-password")
path("reset-password/", ApiResetPasswordView.as_view(), name="api-reset-password")
path("verify/", ApiVerifyView.as_view(), name="api-verify")
path("2fa/enroll/", Api2FAEnrollView.as_view(), name="api-2fa-enroll")
path("2fa/challenge/", Api2FAChallengeView.as_view(), name="api-2fa-challenge")
path("2fa/verify/", Api2FAVerifyView.as_view(), name="api-2fa-verify")
path("2fa/settings/", Api2FASettingsView.as_view(), name="api-2fa-settings")
path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair")
path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh")
path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist")
```

## New Middleware (`backend/apps/accounts/middleware.py`)
### `TwoFactorRequiredMiddleware`
- Runs after `AuthenticationMiddleware`
- If user is authenticated via session but has no verified `TwoFactorMethod`, redirect to `/admin/2fa/enroll/` (unless already on enroll/verify/login/logout/password-reset paths)
- Ensures mandatory 2FA enforcement for HTML panel

## Settings Changes (`backend/config/settings/base.py`)
```
INSTALLED_APPS += ["rest_framework_simplejwt", "rest_framework_simplejwt.token_blacklist"]

# Email (SMTP via env, console fallback for dev)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@finefit.store")

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# REST Framework auth: keep SessionAuthentication for HTML, add JWT for API
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    "rest_framework.authentication.SessionAuthentication",
]

# Session security (already partially set; harden)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# OTP / reset config
OTP_CODE_LENGTH = 6
OTP_CODE_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 1
SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES = 30
```

## New Templates (`backend/templates/admin_panel/`)
| File | Purpose |
|------|---------|
| `forgot_password.html` | Request reset via email or phone |
| `reset_password.html` | Set new password (token-protected) |
| `verify_code.html` | Enter verification code |
| `2fa_enroll.html` | Choose + verify 2FA method |
| `2fa_challenge.html` | OTP challenge during login |
| `2fa_settings.html` | Manage methods + backup codes |

## Security Requirements
- **Code hashing**: Verification codes and backup codes hashed with `make_password`/`check_password` — never plaintext
- **Rate limiting**: Max 3 reset requests per hour per email/phone; max 5 OTP attempts per code
- **Token single-use**: Reset tokens and verification codes invalidated after first successful use
- **CSRF**: All HTML state-changing POSTs require CSRF token; all API mutating endpoints require CSRF (session) or Bearer token (JWT)
- **Session fixation**: `login()` called fresh after credential verification (already done via Django's `login()`)
- **JWT storage**: Access token in memory (JS), refresh token in HttpOnly cookie OR returned in JSON body for client storage
- **Phone masking**: Display only last 4 digits in UI
- **No user enumeration**: Forgot password returns same response whether account exists or not

## User Flows

### Forgot Password
1. User enters email or phone on `/admin/forgot-password/`
2. System creates `PasswordResetRequest` (token), sends reset link (email) or OTP (SMS mock → console)
3. User clicks link / enters code → `/admin/reset-password/<token>/`
4. User sets new password → token invalidated → redirected to login

### Registration Verification
1. Admin creates user via `/admin/admins/create/` → `is_active=False`
2. System generates `VerificationCode` (purpose=registration), sends to email/phone
3. User enters code at `/admin/verify/` → `is_active=True` → can log in

### 2FA Enrollment (mandatory, first login)
1. User logs in with email + password
2. No `TwoFactorMethod` found → redirect to `/admin/2fa/enroll/`
3. User chooses email or SMS, system sends OTP
4. User enters OTP → method enrolled as primary → redirected to dashboard

### 2FA Challenge (every subsequent login)
1. User logs in with email + password
2. Valid `TwoFactorMethod` exists → system sends OTP to enrolled method
3. Redirect to `/admin/2fa/challenge/` → user enters OTP → session established

### Sensitive Actions
1. User attempts change email/phone/password/delete account/change role
2. System checks for fresh verification within `SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES`
3. If not recently verified → send OTP, require code entry before action proceeds

## Implementation Tasks (in order)
1. Add `djangorestframework-simplejwt` to `requirements.txt`
2. Add new models to `backend/apps/accounts/models.py` + migration
3. Add email sending utility (`backend/apps/accounts/utils.py`): send OTP email, send reset email, log SMS to console
4. Add token/password reset views to `backend/apps/accounts/views.py`
5. Add verification views to `backend/apps/accounts/views.py`
6. Add 2FA views (enroll, challenge, settings) to `backend/apps/accounts/views.py`
7. Add JWT token views to `backend/apps/accounts/views.py`
8. Add URL routes in `backend/apps/admin_panel/urls.py` (HTML) and `backend/apps/accounts/urls.py` (API)
9. Add `TwoFactorRequiredMiddleware` to `backend/apps/accounts/middleware.py`
10. Add middleware to `MIDDLEWARE` in settings (after `AuthenticationMiddleware`)
11. Update `settings/base.py`: email, JWT, REST framework, session security, OTP config
12. Create HTML templates (6 files)
13. Update existing login view to redirect to 2FA challenge when user has enrolled method
14. Update sensitive-action views (admin_user_edit, role_edit, etc.) to require re-verification
15. Write tests: password reset, verification, 2FA enroll/challenge, JWT obtain/refresh/blacklist

## Validation Steps
- `python3 manage.py check` → 0 issues
- `python3 manage.py makemigrations --check` → no missing migrations
- `pytest` → all existing + new tests pass
- Forgot password: POST with valid email → 200, reset token created, email logged to console
- Forgot password: POST with nonexistent email → same 200 response (no enumeration)
- Reset password: valid token → new password set, login works with new password
- Reset password: expired/invalid token → 400 error
- Registration: new user → `is_active=False`, verification code sent
- Verification: valid code → `is_active=True`
- Verification: wrong code 5× → code locked, new code required
- 2FA enroll: choose email → OTP sent → verify → `TwoFactorMethod` created
- 2FA challenge: login with enrolled user → OTP sent → verify → session + JWT tokens
- 2FA mandatory: unenrolled user after login → redirected to `/admin/2fa/enroll/`
- JWT: `/api/v1/auth/token/` with valid credentials → access + refresh tokens
- JWT: refresh endpoint → new access token, old refresh blacklisted
- JWT: blacklist endpoint → refresh token invalidated
- Sensitive action: change email without recent verify → OTP required
- CSRF: HTML POST without token → 403; API with Bearer JWT → no CSRF required

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| SMS mock doesn't work in production | Clearly document; production needs Twilio config (env vars) before phone OTP is reliable |
| JWT access token stolen → valid until expiry | Short 15-min access lifetime; refresh token rotation + blacklist |
| Code brute-force | Max 5 attempts, then code locked; rate limit reset requests |
| User enrolls 2FA then loses access to email/phone | Backup codes (8 single-use codes) provided at enrollment |
| Session + JWT both valid simultaneously | Both are independently revocable; logout clears session, blacklist clears refresh |

## Open Questions
None — all design decisions confirmed.