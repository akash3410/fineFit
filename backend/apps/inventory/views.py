"""
Views for the inventory domain.

Provides:
1. Staff StockRecord management & adjustment endpoints (permission gated).
2. Staff StockMovement audit log inspection (strictly read-only).
3. Public variant availability check (safe derived flags, no raw counts).
"""

import uuid

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import ProductVariant
from .exceptions import (
    InsufficientStockError,
    InvalidReservationError,
    InvalidStockAdjustmentError,
    StockRecordNotFoundError,
)
from .models import MovementReason, StockMovement, StockRecord
from .permissions import HasStockMovementPermission, HasStockRecordPermission
from .serializers import (
    PublicVariantAvailabilitySerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
    StockRecordCreateSerializer,
    StockRecordSerializer,
)
from .services import StockService


class StockRecordViewSet(viewsets.ModelViewSet):
    """
    Staff management ViewSet for variant stock balances.

    Allows listing, creating, and adjusting stock records.
    Staff must hold explicit ``inventory.view_stockrecord`` or
    ``inventory.change_stockrecord`` model permissions.
    """

    permission_classes = [HasStockRecordPermission]
    serializer_class = StockRecordSerializer
    lookup_field = "variant_id"

    def get_queryset(self):
        qs = StockRecord.objects.select_related("variant", "variant__product").order_by(
            "-updated_at"
        )
        # Optional filters
        sku = self.request.query_params.get("sku")
        if sku:
            qs = qs.filter(variant__sku__iexact=sku.strip())

        low_stock = self.request.query_params.get("low_stock")
        if low_stock is not None and low_stock.lower() in ("true", "1"):
            qs = qs.low_stock()

        out_of_stock = self.request.query_params.get("out_of_stock")
        if out_of_stock is not None and out_of_stock.lower() in ("true", "1"):
            qs = qs.out_of_stock()

        search = self.request.query_params.get("search")
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(variant__sku__icontains=search)
                | Q(variant__product__title__icontains=search)
            )

        return qs

    def get_object(self):
        variant_id = self.kwargs.get(self.lookup_field)
        try:
            uuid_val = uuid.UUID(str(variant_id))
        except (ValueError, TypeError) as err:
            raise ValidationError({"variant_id": "Invalid variant UUID format."}) from err

        queryset = self.filter_queryset(self.get_queryset())
        filter_kwargs = {self.lookup_field: uuid_val}
        obj = queryset.filter(**filter_kwargs).first()
        if not obj:
            raise ValidationError(
                {"detail": f"StockRecord for variant {variant_id} does not exist."}
            )
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        """Create a new initial StockRecord for a variant."""
        serializer = StockRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            record = StockService.create_stock_record(
                variant_or_id=data["variant_id"],
                quantity_on_hand=data.get("quantity_on_hand", 0),
                quantity_reserved=data.get("quantity_reserved", 0),
                low_stock_threshold=data.get("low_stock_threshold", 5),
                actor=request.user,
                notes=data.get("notes", ""),
                reference_id=data.get("reference_id", ""),
            )
        except InvalidStockAdjustmentError as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = self.get_serializer(record)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="adjust")
    def adjust(self, request, variant_id=None):
        """
        Adjust stock or reservation levels for the specified variant.

        Accepts: action, quantity, reason, notes, reference_id, from_reserved.
        """
        obj = self.get_object()
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        action_type = data["action"]
        quantity = data["quantity"]
        reason = data.get("reason", MovementReason.CORRECTION)
        notes = data.get("notes", "")
        reference_id = data.get("reference_id", "")
        from_reserved = data.get("from_reserved", False)

        try:
            if action_type == "INCREASE":
                updated = StockService.increase_stock(
                    variant_or_id=obj.variant_id,
                    quantity=quantity,
                    reason=reason,
                    actor=request.user,
                    notes=notes,
                    reference_id=reference_id,
                )
            elif action_type == "DECREASE":
                updated = StockService.decrease_stock(
                    variant_or_id=obj.variant_id,
                    quantity=quantity,
                    reason=reason,
                    actor=request.user,
                    notes=notes,
                    reference_id=reference_id,
                    from_reserved=from_reserved,
                )
            elif action_type == "SET":
                updated = StockService.set_stock_level(
                    variant_or_id=obj.variant_id,
                    new_quantity_on_hand=quantity,
                    reason=reason,
                    actor=request.user,
                    notes=notes,
                    reference_id=reference_id,
                )
            elif action_type == "RESERVE":
                updated = StockService.reserve_stock(
                    variant_or_id=obj.variant_id,
                    quantity=quantity,
                    reason=reason,
                    actor=request.user,
                    notes=notes,
                    reference_id=reference_id,
                )
            elif action_type == "RELEASE":
                updated = StockService.release_reservation(
                    variant_or_id=obj.variant_id,
                    quantity=quantity,
                    reason=reason,
                    actor=request.user,
                    notes=notes,
                    reference_id=reference_id,
                )
            else:
                return Response(
                    {"detail": f"Unsupported adjustment action: {action_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (
            InsufficientStockError,
            InvalidReservationError,
            InvalidStockAdjustmentError,
            StockRecordNotFoundError,
        ) as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(updated).data, status=status.HTTP_200_OK)


class StockMovementReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Staff read-only ViewSet for immutable StockMovement audit logs.

    Staff must hold ``inventory.view_stockmovement`` permission.
    """

    permission_classes = [HasStockMovementPermission]
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        qs = StockMovement.objects.select_related("variant", "variant__product", "actor")
        variant_id = self.request.query_params.get("variant_id")
        if variant_id:
            try:
                uuid_val = uuid.UUID(str(variant_id))
                qs = qs.filter(variant_id=uuid_val)
            except (ValueError, TypeError):
                return qs.none()

        reason = self.request.query_params.get("reason")
        if reason:
            qs = qs.filter(reason=reason.strip().upper())

        return qs


class PublicVariantAvailabilityView(APIView):
    """
    Public API endpoint returning derived variant availability status.

    Returns whether an active product variant is in stock, low stock, or out of stock.
    Never exposes exact inventory counts or buffer numbers to the public.
    """

    permission_classes = [AllowAny]

    def get(self, request, variant_id, *args, **kwargs):
        try:
            uuid_val = uuid.UUID(str(variant_id))
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid variant UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        variant = (
            ProductVariant.objects.select_related("stock_record", "product")
            .filter(id=uuid_val, is_active=True, product__is_published=True)
            .first()
        )

        if not variant:
            return Response(
                {"detail": "Variant not found or inactive."},
                status=status.HTTP_404_NOT_FOUND,
            )

        stock_record = getattr(variant, "stock_record", None)
        if stock_record is None:
            # Variant exists but has no stock record: strictly reported out of stock
            data = {
                "variant_id": variant.id,
                "sku": variant.sku,
                "is_in_stock": False,
                "is_low_stock": False,
                "status": "OUT_OF_STOCK",
            }
        else:
            in_stock = stock_record.is_in_stock
            low_stock = stock_record.is_low_stock
            if in_stock:
                stat = "LOW_STOCK" if low_stock else "IN_STOCK"
            else:
                stat = "OUT_OF_STOCK"

            data = {
                "variant_id": variant.id,
                "sku": variant.sku,
                "is_in_stock": in_stock,
                "is_low_stock": low_stock,
                "status": stat,
            }

        serializer = PublicVariantAvailabilitySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

