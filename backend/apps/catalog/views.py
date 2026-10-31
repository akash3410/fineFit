"""
Catalog API views.

Public endpoints (``AllowAny``) never trust a visibility flag on the request;
they constrain the queryset itself so drafts and inactive categories cannot
leak through listings, detail, search, or filters.

Manage endpoints enforce ``ManageModelPermissions`` (model ``view``/``add``/
``change``/``delete``) so that ``is_staff`` alone is never sufficient.
"""

from rest_framework import filters, generics, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from .models import Category, Product, ProductImage, ProductVariant
from .permissions import ManageModelPermissions
from .serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    ProductDetailSerializer,
    ProductImageReadSerializer,
    ProductImageWriteSerializer,
    ProductListSerializer,
    ProductVariantReadSerializer,
    ProductVariantWriteSerializer,
    ProductWriteSerializer,
)


class CatalogPagination(PageNumberPagination):
    """Bounded pagination for product listings (client-overridable)."""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


def _descendant_slugs(category: Category) -> list[str]:
    """Return the category's slug plus all descendant slugs (tree walk)."""
    slugs = [category.slug]
    stack = [category]
    while stack:
        node = stack.pop()
        for child in node.children.all():
            slugs.append(child.slug)
            stack.append(child)
    return slugs


# ---------------------------------------------------------------------------
# Public read endpoints
# ---------------------------------------------------------------------------


class CategoryListView(generics.ListAPIView):
    """Active categories as a nested tree (top-level roots only)."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Category.objects.active().filter(parent=None).prefetch_related("children")


class ProductListView(generics.ListAPIView):
    """
    Published products under active categories, with search, filtering, and
    sorting. Only publicly visible records are ever returned.
    """

    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    pagination_class = CatalogPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["base_price", "created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Product.objects.published()
            .select_related("category")
            .prefetch_related("images")
        )
        params = self.request.query_params

        category_slug = params.get("category")
        if category_slug:
            try:
                category = Category.objects.active().get(slug=category_slug)
            except Category.DoesNotExist:
                return qs.none()
            qs = qs.filter(category__slug__in=_descendant_slugs(category))

        size = params.get("size")
        if size:
            qs = qs.filter(variants__size=size, variants__is_active=True)

        color = params.get("color")
        if color:
            qs = qs.filter(variants__color_name__iexact=color, variants__is_active=True)

        price_min = params.get("price_min")
        if price_min is not None and price_min != "":
            qs = qs.filter(base_price__gte=price_min)

        price_max = params.get("price_max")
        if price_max is not None and price_max != "":
            qs = qs.filter(base_price__lte=price_max)

        return qs.distinct()


class ProductDetailView(generics.RetrieveAPIView):
    """Published product detail by slug (images + active variants). 404 for drafts."""

    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = Product.objects.published().select_related("category").prefetch_related(
        "images", "variants__stock_record"
    )


# ---------------------------------------------------------------------------
# Staff management endpoints (model-permission gated)
# ---------------------------------------------------------------------------


class ManageCategoryViewSet(viewsets.ModelViewSet):
    """CRUD for all categories (including inactive)."""

    queryset = Category.objects.all().prefetch_related("children")
    permission_classes = [ManageModelPermissions]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CategoryWriteSerializer
        return CategorySerializer


class ManageProductViewSet(viewsets.ModelViewSet):
    """CRUD for all products (including drafts)."""

    queryset = (
        Product.objects.all()
        .select_related("category")
        .prefetch_related("images", "variants")
    )
    permission_classes = [ManageModelPermissions]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductWriteSerializer
        return ProductDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Management views expose inactive variants too.
        context["include_all_variants"] = True
        return context


class ManageVariantViewSet(viewsets.ModelViewSet):
    """CRUD for product variants."""

    queryset = ProductVariant.objects.all().select_related("product")
    permission_classes = [ManageModelPermissions]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductVariantWriteSerializer
        return ProductVariantReadSerializer


class ManageImageViewSet(viewsets.ModelViewSet):
    """CRUD for product images."""

    queryset = ProductImage.objects.all().select_related("product", "variant")
    permission_classes = [ManageModelPermissions]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductImageWriteSerializer
        return ProductImageReadSerializer
