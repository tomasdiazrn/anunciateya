from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Deletes test category 'instrumentos' and its listings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm deletion without prompting.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.categories.models import Category
        from apps.listings.models import Listing

        slug = "instrumentos"
        category = Category.objects.filter(slug=slug).first()
        if not category:
            self.stdout.write(self.style.WARNING("Category 'instrumentos' not found. Nothing to do."))
            return

        listing_qs = Listing.objects.filter(category=category)
        listing_count = listing_qs.count()

        if not options["yes"]:
            self.stdout.write(
                self.style.WARNING(
                    f"This will delete {listing_count} listings in category '{slug}' and the category itself."
                )
            )
            self.stdout.write("Re-run with --yes to confirm.")
            return

        listing_qs.delete()
        category.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {listing_count} listings and category '{slug}'.")) 

