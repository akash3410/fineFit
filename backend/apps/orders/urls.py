"""Order API URL configuration.

Endpoints:
  - POST /api/v1/orders/checkout/       -> place a COD order from the current cart
  - GET  /api/v1/orders/                -> the caller's order history
  - GET  /api/v1/orders/{order_number}/ -> one order owned by the caller
  - POST /api/v1/orders/{order_number}/returns/ -> request a return on a
                                                   delivered order
"""

from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="order-list"),
    path("checkout/", views.OrderCheckoutView.as_view(), name="order-checkout"),
    path(
        "<str:order_number>/returns/",
        views.OrderReturnRequestView.as_view(),
        name="order-return-request",
    ),
    path(
        "<str:order_number>/", views.OrderDetailView.as_view(), name="order-detail"
    ),
]
