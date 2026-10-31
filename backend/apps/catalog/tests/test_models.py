"""
Model-level tests for catalog entities: creation, constraints, and validation.

Verifies SKU uniqueness at the database level, price/color validation, the
category cycle guard, the single-primary-image rule, and the image/variant/
product relationship integrity.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import Category, Product, ProductImage, ProductVariant

pytestmark = pytest.mark.django_db


class TestCategory:
    def test_create_and_str(self, category):
        assert category.pk is not None
        assert str(category) == "Outerwear"

    def test_cannot_be_own_parent(self):
        category = Category.objects.create(name="Loop", slug="loop")
        category.parent = category
        with pytest.raises(ValidationError) as exc:
            category.full_clean()
        assert "parent" in exc.value.error_dict

    def test_cannot_move_under_descendant(self, category, child_category):
        # Make the child an ancestor of the parent -> cycle.
        category.parent = child_category
        with pytest.raises(ValidationError) as exc:
            category.full_clean()
        assert "parent" in exc.value.error_dict

    def test_db_rejects_self_parent(self):
        # The CheckConstraint blocks a row whose parent == id at the DB level.
        category = Category.objects.create(name="Selfy", slug="selfy")
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                Category.objects.filter(pk=category.pk).update(parent_id=category.pk)

    def test_slug_unique_at_db(self, category):
        with pytest.raises(IntegrityError):
            Category.objects.create(name="Duplicate", slug="outerwear")

    def test_active_queryset(self, category, inactive_category):
        assert list(Category.objects.active()) == [category]


class TestProduct:
    def test_create_and_str(self, product):
        assert product.pk is not None
        assert str(product) == "Aurora Wool Overcoat"

    def test_base_price_negative_rejected(self, category):
        product = Product(category=category, title="Bad", slug="bad", base_price="-1.00")
        with pytest.raises(ValidationError) as exc:
            product.full_clean()
        assert "base_price" in exc.value.error_dict

    def test_db_rejects_negative_base_price(self, category):
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                Product.objects.create(
                    category=category, title="Bad", slug="bad-db", base_price="-5.00"
                )

    def test_published_queryset_hides_drafts_and_inactive(self, product, draft_product, product_in_inactive_category):
        published = Product.objects.published()
        assert product in published
        assert draft_product not in published
        assert product_in_inactive_category not in published

    def test_slug_unique_at_db(self, product, category):
        with pytest.raises(IntegrityError):
            Product.objects.create(
                category=category, title="Dup", slug="aurora-wool-overcoat", base_price="1.00"
            )


class TestProductVariant:
    def test_sku_unique_at_db(self, product, variant):
        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(product=product, sku="AURORA-M-BLK")

    def test_effective_price_falls_back_to_base(self, product, variant):
        assert variant.effective_price == product.base_price

    def test_effective_price_uses_override(self, product):
        v = ProductVariant.objects.create(
            product=product, sku="AURORA-L-BLK", size="L", price_override="249.00"
        )
        assert v.effective_price == v.price_override

    def test_negative_price_override_rejected(self, product):
        v = ProductVariant(product=product, sku="X", price_override="-1.00")
        with pytest.raises(ValidationError) as exc:
            v.full_clean()
        assert "price_override" in exc.value.error_dict

    def test_db_rejects_negative_price_override(self, product):
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ProductVariant.objects.create(
                    product=product, sku="NEG", price_override="-2.00"
                )

    def test_invalid_color_code_rejected(self, product):
        v = ProductVariant(product=product, sku="BAD-COLOR", color_code="red")
        with pytest.raises(ValidationError) as exc:
            v.full_clean()
        assert "color_code" in exc.value.error_dict

    def test_valid_color_code_accepted(self, product):
        v = ProductVariant(product=product, sku="GOOD-COLOR", color_code="#1F2937")
        v.full_clean()  # should not raise

    def test_duplicate_size_color_rejected(self, product, variant):
        dup = ProductVariant(
            product=product, sku="ANOTHER-SKU", size="M", color_name="Midnight Black"
        )
        with pytest.raises(ValidationError) as exc:
            dup.full_clean()
        assert "size" in exc.value.error_dict


class TestProductImage:
    def test_ordering_deterministic(self, product):
        ProductImage.objects.create(product=product, image="a.png", display_order=2)
        ProductImage.objects.create(product=product, image="b.png", display_order=1)
        orders = [img.display_order for img in product.images.all()]
        assert orders == sorted(orders)

    def test_single_primary_enforced_by_db(self, product):
        ProductImage.objects.create(product=product, image="a.png", is_primary=True)
        with pytest.raises(IntegrityError):
            ProductImage.objects.create(product=product, image="b.png", is_primary=True)

    def test_multiple_non_primary_allowed(self, product):
        ProductImage.objects.create(product=product, image="a.png")
        ProductImage.objects.create(product=product, image="b.png")
        assert product.images.count() == 2

    def test_variant_must_belong_to_product(self, product, variant):
        other = Product.objects.create(
            category=product.category, title="Other", slug="other", base_price="10.00"
        )
        img = ProductImage(product=other, image="x.png", variant=variant)
        with pytest.raises(ValidationError) as exc:
            img.full_clean()
        assert "variant" in exc.value.error_dict
