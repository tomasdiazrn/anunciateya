"""Contrato SEO de anuncios: slug estable, sitemap, redirects y noindex en previews."""

import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.categories.models import Category
from apps.core.sitemaps import ListingSitemap
from apps.listings.category_extensions import PROPERTY_SLUG
from apps.listings.models import Listing, MarketZone, PropertyListing

User = get_user_model()


@override_settings(
    PUBLIC_SITE_URL="https://anunciateya.test",
    SEO_BRAND_NAME="AnunciateYa",
)
class ListingSeoContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="seo_contract_seller@example.com",
            password="test-pass-123",
        )
        cls.hogar = Category.objects.create(name="Hogar", slug="hogar")
        cls.autos = Category.objects.create(name="Autos", slug="autos")
        cls.inmuebles = Category.objects.create(name="Inmuebles", slug=PROPERTY_SLUG)
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

    def _listing(self, *, title="Mesa de madera", status=Listing.Status.PUBLISHED, category=None):
        return Listing.objects.create(
            title=title,
            description="Descripción breve del anuncio.",
            price_amount="100.00",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=category or self.hogar,
            status=status,
        )

    def test_slug_is_immutable_when_title_changes(self):
        listing = self._listing(title="Título original")
        original_slug = listing.slug

        listing.title = "Título completamente nuevo"
        listing.save()
        listing.refresh_from_db()

        self.assertEqual(listing.slug, original_slug)

    def test_published_listing_has_no_noindex_robots(self):
        listing = self._listing()

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="robots"')

    def test_owner_draft_preview_has_noindex(self):
        listing = self._listing(status=Listing.Status.DRAFT)
        self.client.force_login(self.seller)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, nofollow"')

    def test_owner_archived_preview_has_noindex(self):
        listing = self._listing(status=Listing.Status.ARCHIVED)
        self.client.force_login(self.seller)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, nofollow"')

    def test_wrong_category_in_url_redirects_to_canonical(self):
        listing = self._listing()
        wrong_url = f"/autos/{listing.slug}/"

        response = self.client.get(wrong_url)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], listing.get_absolute_url())

    def test_legacy_detail_url_redirects_to_canonical(self):
        listing = self._listing()

        response = self.client.get(f"/listings/{listing.slug}/")

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], listing.get_absolute_url())

    def test_sitemap_includes_published_listing_url(self):
        listing = self._listing()

        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, listing.get_absolute_url())

    def test_sitemap_excludes_draft_listing(self):
        listing = self._listing(status=Listing.Status.DRAFT)

        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f"/hogar/{listing.slug}/")

    def test_sitemap_lastmod_reflects_updated_at(self):
        listing = self._listing()
        listing.title = "Título actualizado sin cambiar slug"
        listing.save()

        sitemap = ListingSitemap()
        items = list(sitemap.items())
        match = next(item for item in items if item.pk == listing.pk)

        self.assertEqual(sitemap.lastmod(match), listing.updated_at)

    def test_meta_title_updates_when_title_changes(self):
        listing = self._listing(title="Título viejo")
        listing.title = "Título nuevo en página"
        listing.save()

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<title>Título nuevo en página | AnunciateYa</title>")
        html = response.content.decode()
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        self.assertIsNotNone(canonical)
        self.assertTrue(canonical.group(1).endswith(listing.get_absolute_url()))

    def test_property_exact_location_adds_json_ld_place_only_when_public(self):
        listing = self._listing(title="Casa exacta", category=self.inmuebles)
        PropertyListing.objects.create(
            listing=listing,
            property_type=PropertyListing.PropertyType.CASA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            address_line="Av. Principal 123",
            address_place_label="Edificio Norte",
            location_precision=PropertyListing.LocationPrecision.EXACT,
            latitude="-2.189400",
            longitude="-79.889100",
        )

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        place = data["offers"]["availableAtOrFrom"]
        self.assertEqual(place["@type"], "Place")
        self.assertEqual(place["address"]["streetAddress"], "Av. Principal 123")
        self.assertEqual(place["geo"]["latitude"], -2.1894)

    def test_property_private_exact_location_omits_json_ld_place(self):
        listing = self._listing(title="Casa privada", category=self.inmuebles)
        PropertyListing.objects.create(
            listing=listing,
            property_type=PropertyListing.PropertyType.CASA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            address_line="Av. Privada 999",
            location_precision=PropertyListing.LocationPrecision.SECTOR,
        )

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertNotIn("availableAtOrFrom", data["offers"])
