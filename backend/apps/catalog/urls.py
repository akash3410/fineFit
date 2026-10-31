"""
Catalog API URL configuration.

Public read endpoints live at ``/api/v1/catalog/``.
Staff management endpoints are isolated under ``/api/v1/catalog/manage/`` so the
draft-visible surface is structurally separate from the public storefront.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"categories", views.ManageCategoryViewSet, basename="manage-category")
router.register(r"products", views.ManageProductViewSet, basename="manage-product")
router.register(r"variants", views.ManageVariantViewSet, basename="manage-variant")
router.register(r"images", views.ManageImageViewSet, basename="manage-image")

urlpatterns = [
    # Public storefront reads
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),
    # Staff management (model-permission gated)
    path("manage/", include(router.urls)),
]
