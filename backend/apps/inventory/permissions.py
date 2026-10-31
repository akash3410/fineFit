"""
Permissions for the inventory domain.

Staff must have explicit inventory model permissions to inspect or mutate records.
``is_staff`` alone is NEVER a substitute for model-level permission verification.
"""

from rest_framework import permissions
from rest_framework.exceptions import NotAuthenticated


class HasStockRecordPermission(permissions.BasePermission):
    """
    Staff model-level permissions for StockRecord management.

    - Read operations (GET/HEAD/OPTIONS) require ``inventory.view_stockrecord``.
    - Adjustment/write operations require ``inventory.change_stockrecord``.
    - Creation requires ``inventory.add_stockrecord``.
    - Deletion requires ``inventory.delete_stockrecord``.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            raise NotAuthenticated()

        if not user.is_staff:
            return False

        if request.method in permissions.SAFE_METHODS:
            return user.has_perm("inventory.view_stockrecord")

        if request.method == "POST":
            # Post could be creating a record or calling an adjustment action
            action = getattr(view, "action", None)
            if action in ("adjust", "reserve", "release"):
                return user.has_perm("inventory.change_stockrecord")
            return user.has_perm("inventory.add_stockrecord")

        if request.method in ("PUT", "PATCH"):
            return user.has_perm("inventory.change_stockrecord")

        if request.method == "DELETE":
            return user.has_perm("inventory.delete_stockrecord")

        return False


class HasStockMovementPermission(permissions.BasePermission):
    """
    Staff model-level permissions for StockMovement audit logs.

    Movement history is immutable and read-only.
    - Read operations require ``inventory.view_stockmovement``.
    - Write/Delete operations are categorically forbidden.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            raise NotAuthenticated()

        if not user.is_staff:
            return False

        if request.method in permissions.SAFE_METHODS:
            return user.has_perm("inventory.view_stockmovement")

        return False
