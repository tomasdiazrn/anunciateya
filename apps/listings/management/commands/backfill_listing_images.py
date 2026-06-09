from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.listings.image_processing import generate_listing_image_variants
from apps.listings.models import ListingImage

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill optimized variants (thumb/medium/large + WebP) for ListingImage rows."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=200)
        parser.add_argument("--max", type=int, default=0, help="Max rows to process (0 = unlimited)")
        parser.add_argument("--start-id", type=int, default=0, help="Process IDs >= start-id")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        batch_size = int(opts["batch_size"] or 200)
        max_rows = int(opts["max"] or 0)
        start_id = int(opts["start_id"] or 0)
        dry = bool(opts["dry_run"])

        qs = (
            ListingImage.objects.filter(id__gte=start_id, image_thumb__isnull=True)
            .exclude(image="")
            .order_by("id")
        )

        processed = 0
        errors = 0

        self.stdout.write(
            f"Backfill listing images: batch_size={batch_size} start_id={start_id} max={max_rows or '∞'} dry_run={dry}"
        )

        while True:
            if max_rows and processed >= max_rows:
                break
            chunk = list(qs[:batch_size])
            if not chunk:
                break

            for li in chunk:
                if max_rows and processed >= max_rows:
                    break
                processed += 1
                try:
                    variants = generate_listing_image_variants(li.image)
                    stem = f"li-{li.listing_id}-{li.pk}"
                    if dry:
                        continue
                    with transaction.atomic():
                        li.image_thumb.save(f"{stem}-thumb.jpg", variants["thumb"].content, save=False)
                        li.image_thumb_webp.save(f"{stem}-thumb.webp", variants["thumb_webp"].content, save=False)
                        li.image_medium.save(f"{stem}-medium.jpg", variants["medium"].content, save=False)
                        li.image_medium_webp.save(f"{stem}-medium.webp", variants["medium_webp"].content, save=False)
                        li.image_large.save(f"{stem}-large.jpg", variants["large"].content, save=False)
                        li.image_large_webp.save(f"{stem}-large.webp", variants["large_webp"].content, save=False)
                        li.save(
                            update_fields=[
                                "image_thumb",
                                "image_thumb_webp",
                                "image_medium",
                                "image_medium_webp",
                                "image_large",
                                "image_large_webp",
                            ]
                        )
                except Exception as e:
                    errors += 1
                    msg = f"[{li.id}] listing={li.listing_id} ERROR: {e}"
                    self.stderr.write(msg)
                    log.exception(msg)

            # advance cursor
            last_id = chunk[-1].id
            qs = qs.filter(id__gt=last_id)

        self.stdout.write(f"Done. processed={processed} errors={errors}")

