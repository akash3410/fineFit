from django.urls import path
from .views import CSRFTokenView, CurrentUserView, SessionLoginView, SessionLogoutView

app_name = "accounts"

urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf-token"),
    path("login/", SessionLoginView.as_view(), name="session-login"),
    path("logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]
