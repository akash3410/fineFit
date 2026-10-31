"""
Product image tests: ordering, the single-primary rule, and file validation.

Covers upload size/type/dimension limits and the deterministic ordering /
primary-image constraints.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.catalog.models import ProductImage
from apps.catalog.tests.conftest import make_image_file

pytestmark = pytest.mark.django_db


def _manage_images_url(pk=None):
    base = reverse("manage-image-list")
    return f"{base}{pk}/" if pk is not None else base


class TestImageUploadValidation:
    def test_valid_image_upload_succeeds(self, catalog_manager_client, product):
        response = catalog_manager_client.post(
            _manage_images_url(),
            {"product": product.pk, "image": make_image_file()},
        )
        assert response.status_code == 201
        assert ProductImage.objects.filter(product=product).count() == 1

    def test_oversized_file_rejected(self, catalog_manager_client, product):
        big = SimpleUploadedFile(
            "big.png", b"x" * (6 * 1024 * 1024), content_type="image/png"
        )
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": big}
        )
        assert response.status_code == 400
        assert "image" in response.data

    def test_disguised_non_image_rejected(self, catalog_manager_client, product):
        fake = SimpleUploadedFile("fake.png", b"not-an-image", content_type="image/png")
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": fake}
        )
        assert response.status_code == 400
        assert "image" in response.data

    def test_disallowed_format_rejected(self, catalog_manager_client, product):
        gif = SimpleUploadedFile("anim.gif", b"R0lGODlhAQABAAAAACw=", content_type="image/gif")
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": gif}
        )
        assert response.status_code == 400
        assert "image" in response.data

    def test_oversized_dimensions_rejected(self, catalog_manager_client, product):
        wide = make_image_file(name="wide", size=(9000, 10))
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": wide}
        )
        assert response.status_code == 400
        assert "image" in response.data


class TestPrimaryImageRule:
    def test_second_primary_rejected(self, catalog_manager_client, product):
        catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": make_image_file("a"), "is_primary": "true"}
        )
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": make_image_file("b"), "is_primary": "true"}
        )
        assert response.status_code == 400
        assert "is_primary" in response.data

    def test_primary_on_different_products_allowed(self, catalog_manager_client, product, category):
        from apps.catalog.models import Product

        other = Product.objects.create(
            category=category, title="Another", slug="another", base_price="10.00"
        )
        r1 = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": make_image_file("a"), "is_primary": "true"}
        )
        r2 = catalog_manager_client.post(
            _manage_images_url(), {"product": other.pk, "image": make_image_file("b"), "is_primary": "true"}
        )
        assert r1.status_code == 201
        assert r2.status_code == 201


class TestImageMediaServing:
    def test_uploaded_image_url_returns_file_and_200(self, catalog_manager_client, product):
        """
        End-to-end: the URL the API returns must resolve to a stored file and be
        servable by the same ``django.views.static.serve`` view that
        ``config.urls`` wires up for ``MEDIA_URL`` in development.

        Serving is exercised directly against the test's redirected ``MEDIA_ROOT``
        because ``config.urls`` captures its document_root at import time.
        """
        upload = make_image_file()
        response = catalog_manager_client.post(
            _manage_images_url(), {"product": product.pk, "image": upload}
        )
        assert response.status_code == 201

        url = response.data["image"]
        assert url.startswith("http://testserver/media/")
        assert url.endswith(".png")

        from django.conf import settings as dj_settings
        from django.core.files.storage import default_storage
        from django.test import RequestFactory
        from django.views.static import serve as static_serve

        # The relational path must resolve to a real file under MEDIA_ROOT,
        # with stored bytes matching the uploaded payload.
        rel_path = url.split("/media/", 1)[1]
        assert default_storage.exists(rel_path)
        stored = default_storage.open(rel_path).read()
        upload.seek(0)
        assert stored == upload.read()

        # The dev media-serving view must return the stored file.
        request = RequestFactory().get(url)
        served = static_serve(request, rel_path, document_root=str(dj_settings.MEDIA_ROOT))
        assert served.status_code == 200
        assert "image/png" in served["Content-Type"]
        streamed = b"".join(served.streaming_content)
        assert streamed == stored


class TestImageVariantRelationship:
    def test_variant_from_other_product_rejected(self, catalog_manager_client, product, variant):
        from apps.catalog.models import Product

        other = Product.objects.create(
            category=product.category, title="Other", slug="other-img", base_price="10.00"
        )
        response = catalog_manager_client.post(
            _manage_images_url(),
            {"product": other.pk, "variant": variant.pk, "image": make_image_file()},
        )
        assert response.status_code == 400
        assert "variant" in response.data


class TestImageOrdering:
    def test_ordering_by_display_order(self, product):
        ProductImage.objects.create(product=product, image="b.png", display_order=2)
        ProductImage.objects.create(product=product, image="a.png", display_order=1)
        orders = [img.display_order for img in product.images.all()]
        assert orders == [1, 2]
