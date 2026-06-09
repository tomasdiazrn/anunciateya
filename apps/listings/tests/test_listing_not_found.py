from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.categories.models import Category
from apps.listings.models import Listing

User = get_user_model()


class ListingNotFoundTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="listing_not_found_seller@example.com",
            password="test-pass-123",
        )
        cls.category = Category.objects.create(name="Hogar", slug="hogar")

    def _listing(self, status):
        return Listing.objects.create(
            title=f"Anuncio {status}",
            description="Detalle breve",
            price_amount="100.00",
            currency="USD",
            location="Guayaquil",
            seller=self.seller,
            category=self.category,
            status=status,
        )

    def test_draft_listing_renders_listing_404_for_visitors(self):
        listing = self._listing(Listing.Status.DRAFT)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Anuncio no disponible", status_code=404)
        self.assertContains(response, "Ir al home", status_code=404)

    def test_archived_listing_renders_listing_404_for_visitors(self):
        listing = self._listing(Listing.Status.ARCHIVED)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Anuncio no disponible", status_code=404)

    def test_owner_can_view_draft_listing(self):
        listing = self._listing(Listing.Status.DRAFT)
        self.client.force_login(self.seller)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solo tú ves este anuncio")

    def test_legacy_detail_uses_listing_404_for_unpublished_visitors(self):
        listing = self._listing(Listing.Status.DRAFT)

        response = self.client.get(f"/listings/{listing.slug}/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Anuncio no disponible", status_code=404)
