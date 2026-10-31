"""
Cart API URL configuration.

All cart routes operate on the CURRENT cart resolved from request identity
(authenticated customer or guest session). No cart/owner identifiers appear
in URLs, and no session keys are accepted from payloads.

Endpoints:
  - GET    /api/v1/cart/           -> retrieve current cart (auto-creates)
  - DELETE /api/v1/cart/           -> clear all items
  - POST   /api/v1/cart/clear/     -> clear all items (verb alternative)
  - POST   /api/v1/cart/items/     -> add a variant
  - PATCH  /api/v1/cart/items/{id}/ -> update quantity
  - DELETE /api/v1/cart/items/{id}/ -> remove item
"""

from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.CartDetailView.as_view(), name="cart-detail"),
    path("clear/", views.CartClearView.as_view(), name="cart-clear"),
    path("items/", views.CartItemAddView.as_view(), name="cart-item-add"),
    path(
        "items/<str:identifier>/",
        views.CartItemDetailView.as_view(),
        name="cart-item-detail",
    ),
]
