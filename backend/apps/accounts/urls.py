from django.urls import path
from .views import (
    CSRFTokenView,
    CurrentUserView,
    SessionLoginView,
    SessionLogoutView,
    ApiForgotPasswordView,
    ApiResetPasswordView,
    ApiVerifyView,
    Api2FAEnrollView,
    Api2FAChallengeView,
    Api2FAVerifyView,
    Api2FASettingsView,
    ApiTokenObtainPairView,
    ApiTokenRefreshView,
    ApiTokenBlacklistView,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("login/", SessionLoginView.as_view(), name="session-login"),
    path("logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    
    # Password reset (API)
    path("forgot-password/", ApiForgotPasswordView.as_view(), name="api-forgot-password"),
    path("reset-password/", ApiResetPasswordView.as_view(), name="api-reset-password"),
    
    # Verification (API)
    path("verify/", ApiVerifyView.as_view(), name="api-verify"),
    
    # Two-factor authentication (API)
    path("2fa/enroll/", Api2FAEnrollView.as_view(), name="api-2fa-enroll"),
    path("2fa/challenge/", Api2FAChallengeView.as_view(), name="api-2fa-challenge"),
    path("2fa/verify/", Api2FAVerifyView.as_view(), name="api-2fa-verify"),
    path("2fa/settings/", Api2FASettingsView.as_view(), name="api-2fa-settings"),
    
    # JWT token endpoints
    path("token/", ApiTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", ApiTokenRefreshView.as_view(), name="token_refresh"),
    path("token/blacklist/", ApiTokenBlacklistView.as_view(), name="token_blacklist"),
]
