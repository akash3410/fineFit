"""
Backfill ``StockRecord`` rows from the stock quantity declared on catalog variants.

The staff dashboard has always written ``ProductVariant.stock`` while inventory
balances live in ``StockRecord``. Variants created that way therefore had no
inventory balance, which made the storefront show them as purchasable while the
cart rejected them with "currently unavailable".

This migration establishes an initial balance (and matching ledger movement) for
every variant that has declared stock but no ``StockRecord`` yet.
"""

from django.db import migrations

DEFAULT_LOW_STOCK_THRESHOLD = 5
INITIAL_STOCK_REASON = "INITIAL_STOCK"


def backfill_stock_records(apps, schema_editor):
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    StockRecord = apps.get_model("inventory", "StockRecord")
    StockMovement = apps.get_model("inventory", "StockMovement")

    variants = ProductVariant.objects.filter(stock_record__isnull=True, stock__gt=0)

    for variant in variants.iterator():
        record = StockRecord.objects.create(
            variant_id=variant.pk,
            quantity_on_hand=variant.stock,
            quantity_reserved=0,
            low_stock_threshold=DEFAULT_LOW_STOCK_THRESHOLD,
        )
        StockMovement.objects.create(
            stock_record_id=record.pk,
            variant_id=variant.pk,
            quantity_delta=variant.stock,
            reserved_delta=0,
            reason=INITIAL_STOCK_REASON,
            notes="Initial balance backfilled from catalog variant stock.",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_event_end_at_no_default_title_200"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_stock_records, migrations.RunPython.noop),
    ]
