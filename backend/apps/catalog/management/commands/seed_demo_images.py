"""
Attach demo images to catalog records that are missing them.

``seed_demo_catalog`` deliberately creates no ``ProductImage`` rows and leaves
``Subcategory.image`` / ``Event.image`` empty, so a freshly seeded database
renders the storefront with empty placeholders even though image files already
exist under ``MEDIA_ROOT``. This command closes that gap for local development.

Source files are located by content hash rather than by path because
``MEDIA_ROOT`` is gitignored: on a fresh clone the files may be absent, in which
case the command reports what it skipped instead of failing.

The command only ever *fills empty* slots - it never overwrites an image that a
staff member has already uploaded - so it is safe to re-run.
"""

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import Category, Event, Product, ProductImage, Subcategory

# Content hashes of the curated demo images, in preference order per target.
# Matching on hash (instead of a hard-coded relative path) keeps the command
# working regardless of where ``upload_to`` happened to store the file.
DEMO_IMAGE_HASHES: dict[str, list[str]] = {
    # "WINTER COLLECTION" poster - reads as a fashion campaign graphic.
    "product": ["4db908842f24fbca391ca18f28b47265"],
    # Same artwork at thumbnail resolution - suits the subcategory strip.
    "subcategory": ["b2a29d320574cb99d728b8e629c6f33f"],
    # Storefront screenshot - reads as a sale/announcement banner.
    "event": ["0c29bb806fe0c6b146611d3390023a69"],
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# Demo events get a 90-day window starting today when their stored window is
# inverted (``end_at`` before ``start_at``), which makes them permanently
# invisible to ``Event.objects.active()``.
REPAIRED_WINDOW_DAYS = 90


class Command(BaseCommand):
    help = "Attach demo images to products, subcategories and events missing them (dev only)"

    def handle(self, *args, **options):
        # Same production guard as the other seed commands.
        if getattr(settings, "ENVIRONMENT", "").lower() == "production":
            raise CommandError("Refusing to run seed_demo_images in production environment.")
        if getattr(settings, "DEBUG") is False:
            raise CommandError("Refusing to run seed_demo_images in production settings (DEBUG=False).")

        sources = self._index_media_files(Path(settings.MEDIA_ROOT))
        if not sources:
            self.stdout.write(
                self.style.WARNING(
                    "No demo image files found under MEDIA_ROOT - nothing to attach."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("Attaching demo images..."))

        self._fill_products(sources)
        self._fill_subcategories(sources)
        self._fill_events(sources)
        self._repair_event_dates()

        self.stdout.write(
            self.style.SUCCESS(
                "\nDemo images attached!\n"
                f"ProductImage rows: {ProductImage.objects.count()}, "
                f"Categories with image: {Category.objects.exclude(image='').count()}, "
                f"Subcategories with image: {Subcategory.objects.exclude(image='').count()}, "
                f"Events with image: {Event.objects.exclude(image='').count()}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "\nNote: these are placeholder graphics, not product photography. "
                "Replace them with properly licensed images before going live."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index_media_files(self, media_root: Path) -> dict[str, Path]:
        """Map ``{md5: path}`` for every image file below ``media_root``."""
        if not media_root.exists():
            return {}

        indexed: dict[str, Path] = {}
        for path in sorted(media_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            digest = hashlib.md5(path.read_bytes()).hexdigest()
            indexed.setdefault(digest, path)  # first occurrence wins
        return indexed

    def _resolve(self, hashes: list[str], sources: dict[str, Path]) -> list[tuple[Path, bytes]]:
        """Return ``(path, content)`` for every requested hash that exists."""
        resolved: list[tuple[Path, bytes]] = []
        for digest in hashes:
            path = sources.get(digest)
            if path is None:
                self.stdout.write(
                    f"  {self.style.WARNING('skip')} source image {digest[:8]}... "
                    "not present in MEDIA_ROOT"
                )
                continue
            resolved.append((path, path.read_bytes()))
        return resolved

    def _fill_products(self, sources: dict[str, Path]) -> None:
        """Give every imageless product a primary image."""
        files = self._resolve(DEMO_IMAGE_HASHES["product"], sources)
        if not files:
            return

        products = Product.objects.filter(is_deleted=False, images__isnull=True).distinct()
        for index, product in enumerate(products):
            path, content = files[index % len(files)]
            ProductImage.objects.create(
                product=product,
                image=ContentFile(content, name=path.name),
                alt_text=product.title,
                display_order=0,
                is_primary=True,
            )
            self.stdout.write(f"  product '{product.slug}' -> {path.name}")

    def _fill_subcategories(self, sources: dict[str, Path]) -> None:
        """Give every subcategory without an image one."""
        files = self._resolve(DEMO_IMAGE_HASHES["subcategory"], sources)
        if not files:
            return

        for index, subcategory in enumerate(Subcategory.objects.filter(image="")):
            path, content = files[index % len(files)]
            subcategory.image = ContentFile(content, name=path.name)
            subcategory.save(update_fields=["image"])
            self.stdout.write(f"  subcategory '{subcategory.slug}' -> {path.name}")

    def _fill_events(self, sources: dict[str, Path]) -> None:
        """Give every event without an image one."""
        files = self._resolve(DEMO_IMAGE_HASHES["event"], sources)
        if not files:
            return

        for index, event in enumerate(Event.objects.filter(image="")):
            path, content = files[index % len(files)]
            event.image = ContentFile(content, name=path.name)
            event.save(update_fields=["image"])
            self.stdout.write(f"  event '{event.slug}' -> {path.name}")

    def _repair_event_dates(self) -> None:
        """Reset inverted date windows so the event can ever become active."""
        now = timezone.now()
        for event in Event.objects.all():
            if event.start_at is None or event.end_at is None:
                continue
            if event.end_at >= event.start_at:
                continue

            old_start, old_end = event.start_at, event.end_at
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            event.start_at = start
            event.end_at = start + timezone.timedelta(days=REPAIRED_WINDOW_DAYS)
            event.save(update_fields=["start_at", "end_at"])
            self.stdout.write(
                f"  event '{event.slug}' window {old_start:%Y-%m-%d}..{old_end:%Y-%m-%d} "
                f"is inverted -> repaired to {event.start_at:%Y-%m-%d}..{event.end_at:%Y-%m-%d}"
            )
