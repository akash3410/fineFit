"""
URL configuration for FineFit E-Commerce backend.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from apps.dashboard import views

urlpatterns = [
    path("admin/", include(("apps.admin_panel.urls", "admin_panel"), namespace="admin_panel")),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.cart.urls")),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
