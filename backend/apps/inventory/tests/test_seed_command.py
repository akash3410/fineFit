"""
Tests for the development-only seed_demo_inventory management command.
"""

from io import StringIO
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.inventory.models import StockRecord


@pytest.mark.django_db
class TestSeedDemoInventoryCommand:
    def test_refuses_production_environment(self, settings, variant):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = True
        with pytest.raises(CommandError, match="Refusing to run seed_demo_inventory in production environment"):
            call_command("seed_demo_inventory")

    def test_refuses_production_settings_debug_false(self, settings, variant):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = False
        with pytest.raises(CommandError, match="Refusing to run seed_demo_inventory in production settings"):
            call_command("seed_demo_inventory")

    def test_seeds_inventory_in_development(self, settings, variant, variant_two):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = True
        out = StringIO()

        call_command("seed_demo_inventory", "--default-quantity=30", "--low-threshold=8", stdout=out)
        output = out.getvalue()

        assert "2 created" in output
        sr1 = StockRecord.objects.get(variant=variant)
        assert sr1.quantity_on_hand == 30
        assert sr1.low_stock_threshold == 8

        # Idempotence test: running again skips existing records
        out2 = StringIO()
        call_command("seed_demo_inventory", stdout=out2)
        assert "2 skipped" in out2.getvalue()

    def test_force_reset_option(self, settings, variant):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = True
        StockRecord.objects.create(variant=variant, quantity_on_hand=100)

        out = StringIO()
        call_command("seed_demo_inventory", "--default-quantity=15", "--force-reset", stdout=out)
        assert "1 reset" in out.getvalue()

        sr = StockRecord.objects.get(variant=variant)
        assert sr.quantity_on_hand == 15

