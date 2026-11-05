"""Staff dashboard views for customer orders.

The custom admin panel lists cash-on-delivery orders placed on the storefront,
shows the delivery details and line snapshots, and lets staff advance the order
status. Status changes go through ``OrderService`` so cancellations return the
units to stock instead of silently losing inventory.
"""

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.orders.exceptions import OrderValidationError
from apps.orders.models import Order, OrderStatus, ReturnRequest
from apps.orders.services import RETURNABLE_STATUSES, OrderService

from .decorators import admin_access_required


@user_passes_test(admin_access_required)
def order_list(request):
    queryset = Order.objects.prefetch_related("items").order_by("-created_at")

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search)
            | Q(customer_name__icontains=search)
            | Q(customer_phone__icontains=search)
            | Q(customer_email__icontains=search)
        )
    if status in OrderStatus.values:
        queryset = queryset.filter(status=status)

    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    status_counts = {
        row["status"]: row["total"]
        for row in Order.objects.values("status").annotate(total=Count("id"))
    }

    return render(
        request,
        "admin_panel/orders/index.html",
        {
            "page_obj": page_obj,
            "search": search,
            "selected_status": status,
            "statuses": OrderStatus.choices,
            "status_counts": status_counts,
            "total_orders": sum(status_counts.values()),
            "pending_orders": status_counts.get(OrderStatus.PENDING, 0),
        },
    )


@user_passes_test(admin_access_required)
def order_view(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), order_number=order_number
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "return":
            _handle_return(request, order)
        elif action in ("approve_return", "decline_return"):
            _handle_return_review(
                request, order, approve=action == "approve_return"
            )
        else:
            _handle_status_update(request, order)
        return redirect("admin_panel:order_view", order_number=order.order_number)

    items = list(order.items.all())
    return_requests = list(
        order.return_requests.select_related("requested_by", "resolved_by")
        .prefetch_related("items__order_item")
        .order_by("-created_at")
    )
    return render(
        request,
        "admin_panel/orders/view.html",
        {
            "order": order,
            "items": items,
            "statuses": OrderStatus.choices,
            "address": order.shipping_address or {},
            "is_terminal": order.status
            in (OrderStatus.CANCELLED, OrderStatus.RETURNED),
            "can_return": order.status in RETURNABLE_STATUSES,
            "returnable_items": [item for item in items if item.remaining_quantity],
            "status_changes": order.status_changes.select_related("changed_by"),
            "returned_units": sum(item.returned_quantity for item in items),
            "return_requests": return_requests,
            "open_return_requests": [
                return_request
                for return_request in return_requests
                if return_request.is_open
            ],
        },
    )


def _handle_status_update(request, order: Order) -> None:
    """Apply a fulfilment status change and report the outcome."""
    new_status = request.POST.get("status", "").strip()
    note = request.POST.get("note", "").strip()
    try:
        OrderService.update_status(
            order.pk, new_status, actor=request.user, note=note
        )
    except OrderValidationError as exc:
        messages.error(request, str(exc))
        return
    order.refresh_from_db()
    messages.success(
        request,
        f"Order {order.order_number} marked as "
        f"{order.get_status_display().lower()}.",
    )


def _handle_return_review(request, order: Order, *, approve: bool) -> None:
    """Approve (restock) or decline a customer's return request."""
    return_request = ReturnRequest.objects.filter(
        pk=request.POST.get("return_request_id", "").strip() or None, order=order
    ).first()
    if return_request is None:
        messages.error(request, "That return request no longer exists.")
        return

    try:
        OrderService.review_return_request(
            return_request.pk,
            approve=approve,
            actor=request.user,
            note=request.POST.get("note", "").strip(),
        )
    except OrderValidationError as exc:
        messages.error(request, str(exc))
        return

    if approve:
        messages.success(
            request,
            f"Return request approved: {return_request.total_quantity} unit(s) "
            f"for order {order.order_number} are back in stock.",
        )
    else:
        messages.success(
            request,
            f"Return request declined for order {order.order_number}.",
        )


def _handle_return(request, order: Order) -> None:
    """Record a line-level return from the ``return_qty_<item id>`` inputs."""
    quantities: dict[int, int] = {}
    for key, value in request.POST.items():
        if not key.startswith("return_qty_"):
            continue
        value = value.strip()
        if not value:
            continue
        try:
            item_id = int(key.removeprefix("return_qty_"))
            quantity = int(value)
        except ValueError:
            messages.error(request, "Return quantities must be whole numbers.")
            return
        if quantity:
            quantities[item_id] = quantity

    note = request.POST.get("note", "").strip()
    try:
        OrderService.return_items(
            order.pk, quantities, actor=request.user, note=note
        )
    except OrderValidationError as exc:
        messages.error(request, str(exc))
        return

    order.refresh_from_db()
    messages.success(
        request,
        f"Return recorded for order {order.order_number} "
        f"({sum(quantities.values())} unit(s) back in stock).",
    )
