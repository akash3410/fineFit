"""
Seed demo inventory data for development environments.

This command is strictly for local/development environments and REFUSES to run
in production or when DEBUG=False.

It is idempotent: variants that already have a StockRecord are skipped unless
the ``--force-reset`` option is explicitly specified.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import ProductVariant
from apps.inventory.models import MovementReason, StockRecord
from apps.inventory.services import StockService


class Command(BaseCommand):
    help = "Seed demo inventory stock records for local development (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--default-quantity",
            type=int,
            default=25,
            help="Default physical on-hand quantity to assign (default: 25).",
        )
        parser.add_argument(
            "--low-threshold",
            type=int,
            default=5,
            help="Default low stock threshold to assign (default: 5).",
        )
        parser.add_argument(
            "--force-reset",
            action="store_true",
            help="Reset existing stock records to default quantities instead of skipping.",
        )

    def handle(self, *args, **options):
        # Strict protection against execution in production environments
        if getattr(settings, "ENVIRONMENT", "").lower() == "production":
            raise CommandError("Refusing to run seed_demo_inventory in production environment.")
        if getattr(settings, "DEBUG", True) is False:
            raise CommandError(
                "Refusing to run seed_demo_inventory in production settings (DEBUG=False)."
            )

        default_qty = options["default_quantity"]
        low_threshold = options["low_threshold"]
        force_reset = options["force_reset"]

        if default_qty < 0 or low_threshold < 0:
            raise CommandError("Quantities and thresholds must be non-negative integers.")

        variants = ProductVariant.objects.select_related("stock_record").order_by("sku")
        total_variants = variants.count()

        if total_variants == 0:
            self.stdout.write(
                self.style.WARNING("No product variants found in catalog. Run seed_demo_catalog first.")
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Processing demo inventory for {total_variants} variants "
                f"(default_qty={default_qty}, low_threshold={low_threshold}, force_reset={force_reset})..."
            )
        )

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for variant in variants:
                stock_record = getattr(variant, "stock_record", None)
                if stock_record is None:
                    StockService.create_stock_record(
                        variant_or_id=variant,
                        quantity_on_hand=default_qty,
                        quantity_reserved=0,
                        low_stock_threshold=low_threshold,
                        reason=MovementReason.INITIAL_STOCK,
                        notes="Demo inventory seeded via seed_demo_inventory command.",
                    )
                    created_count += 1
                elif force_reset:
                    StockService.set_stock_level(
                        variant_or_id=variant,
                        new_quantity_on_hand=default_qty,
                        reason=MovementReason.CORRECTION,
                        notes="Demo inventory reset via seed_demo_inventory --force-reset.",
                    )
                    updated_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo inventory seeding complete: "
                f"{created_count} created, {updated_count} reset, {skipped_count} skipped."
            )
        )

