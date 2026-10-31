"""
URL routing configuration for the inventory domain.

Provides:
- Public storefront availability: ``/api/v1/inventory/availability/<variant_id>/``
- Staff stock record operations: ``/api/v1/inventory/records/``
- Staff stock adjustment action: ``/api/v1/inventory/records/<variant_id>/adjust/``
- Staff audit movement log: ``/api/v1/inventory/movements/``
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"records", views.StockRecordViewSet, basename="stock-record")
router.register(r"movements", views.StockMovementReadOnlyViewSet, basename="stock-movement")

urlpatterns = [
    path("availability/<uuid:variant_id>/", views.PublicVariantAvailabilityView.as_view(), name="variant-availability"),
    path("", include(router.urls)),
]

