from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"
    verbose_name = _("Product Catalog")

    def ready(self):
        # Register signal handlers (e.g. media cleanup on image deletion).
        import apps.catalog.signals  # noqa: F401
