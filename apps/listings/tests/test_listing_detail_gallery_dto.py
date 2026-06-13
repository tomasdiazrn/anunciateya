"""Galería de detalle: orden desde prefetch y campos del DTO (sin query extra en lectura)."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.categories.models import Category
from apps.listings.category_engine_queryplan import LISTING_DETAIL_ORM_PLAN, apply_query_plan
from apps.listings.category_extensions import PROPERTY_SLUG
from apps.listings.listing_detail_dto import build_listing_detail_context, ordered_listing_image_urls
from apps.listings.models import Listing, ListingImage, MarketZone, PropertyListing

User = get_user_model()

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ListingDetailGalleryDtoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="gallery_dto_seller@example.com",
            password="test-pass-123",
        )
        cls.cat, _ = Category.objects.get_or_create(
            slug="hogar",
            defaults={"name": "Hogar", "order": 0},
        )
        cls.property_cat, _ = Category.objects.get_or_create(
            slug=PROPERTY_SLUG,
            defaults={"name": "Inmuebles", "order": 1},
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

    def _published_listing(self, title: str, *, category: Category | None = None) -> Listing:
        return Listing.objects.create(
            title=title,
            description="d",
            price_amount="100.00",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=category or self.cat,
            status=Listing.Status.PUBLISHED,
        )

    def _with_detail_plan(self, listing: Listing) -> Listing:
        return apply_query_plan(
            Listing.objects.filter(pk=listing.pk),
            LISTING_DETAIL_ORM_PLAN,
        ).first()

    def test_zero_images_placeholder_dto(self):
        listing = self._published_listing("Sin fotos")
        listing = self._with_detail_plan(listing)
        ctx = build_listing_detail_context(listing, trust_map={})
        self.assertEqual(ctx.gallery_count, 0)
        self.assertFalse(ctx.gallery_has_multiple)
        self.assertTrue(ctx.gallery_show_placeholder)
        self.assertEqual(ctx.gallery_images, ())
        self.assertEqual(ctx.thumbnail_images, ())

    def test_detail_location_keeps_reference_separate(self):
        listing = self._published_listing("Con referencia")
        listing.location_reference = "frente al kiosco x9"
        listing.save(update_fields=["location_reference", "updated_at"])
        listing = self._with_detail_plan(listing)

        ctx = build_listing_detail_context(listing, trust_map={})

        self.assertEqual(ctx.location, self.zone.name)
        self.assertEqual(ctx.location_reference, "frente al kiosco x9")
        self.assertNotIn("frente al kiosco x9", ctx.location)

    def test_property_exact_location_context_is_public_when_enabled(self):
        listing = self._published_listing("Casa con mapa", category=self.property_cat)
        PropertyListing.objects.create(
            listing=listing,
            property_type=PropertyListing.PropertyType.CASA,
            operation_type=PropertyListing.OperationType.VENTA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            address_line="Av. Principal 123",
            address_place_label="Edificio Norte",
            location_precision=PropertyListing.LocationPrecision.EXACT,
            latitude="-2.189400",
            longitude="-79.889100",
        )
        listing = self._with_detail_plan(listing)

        ctx = build_listing_detail_context(listing, trust_map={})

        self.assertEqual(ctx.property_location_title, "Dirección del inmueble")
        self.assertIn("Av. Principal 123", ctx.property_location_address)
        self.assertTrue(ctx.property_show_map)
        self.assertEqual(ctx.property_map_latitude, "-2.189400")
        self.assertEqual(ctx.property_map_longitude, "-79.889100")

    def test_property_sector_precision_hides_exact_address_context(self):
        listing = self._published_listing("Casa sin mapa", category=self.property_cat)
        PropertyListing.objects.create(
            listing=listing,
            property_type=PropertyListing.PropertyType.CASA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            address_line="Av. Privada 999",
            location_precision=PropertyListing.LocationPrecision.SECTOR,
        )
        listing = self._with_detail_plan(listing)

        ctx = build_listing_detail_context(listing, trust_map={})

        self.assertEqual(ctx.property_location_address, "")
        self.assertFalse(ctx.property_show_map)

    def test_property_approximate_location_does_not_expose_coordinates(self):
        listing = self._published_listing("Casa aproximada", category=self.property_cat)
        PropertyListing.objects.create(
            listing=listing,
            property_type=PropertyListing.PropertyType.CASA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            address_place_label="Conjunto privado",
            location_precision=PropertyListing.LocationPrecision.APPROXIMATE,
            latitude="-2.189400",
            longitude="-79.889100",
        )
        listing = self._with_detail_plan(listing)

        ctx = build_listing_detail_context(listing, trust_map={})

        self.assertEqual(ctx.property_location_title, "Ubicación aproximada")
        self.assertEqual(ctx.property_location_address, "Conjunto privado")
        self.assertEqual(ctx.property_map_latitude, "")
        self.assertEqual(ctx.property_map_longitude, "")
        self.assertFalse(ctx.property_show_map)

    def test_sort_order_matches_prefetch_order(self):
        listing = self._published_listing("Con fotos")
        up = SimpleUploadedFile("a.png", _PNG_1X1, content_type="image/png")
        ListingImage.objects.create(listing=listing, image=up, sort_order=10)
        up2 = SimpleUploadedFile("b.png", _PNG_1X1, content_type="image/png")
        ListingImage.objects.create(listing=listing, image=up2, sort_order=0)
        listing = self._with_detail_plan(listing)
        imgs = list(ListingImage.objects.filter(listing_id=listing.pk))
        imgs.sort(key=lambda im: (im.sort_order, im.pk))
        self.assertEqual([im.sort_order for im in imgs], [0, 10])
        expected = tuple(str(x.image.url) for x in imgs)
        urls = ordered_listing_image_urls(listing)
        self.assertEqual(urls, expected)
        ctx = build_listing_detail_context(listing, trust_map={})
        self.assertEqual(ctx.gallery_images, urls)
        self.assertEqual(ctx.thumbnail_images, urls)
        self.assertEqual(ctx.gallery_count, 2)
        self.assertTrue(ctx.gallery_has_multiple)
        self.assertFalse(ctx.gallery_show_placeholder)
        self.assertTrue(ctx.gallery_mosaic)
        self.assertEqual(ctx.gallery_mosaic_hero, urls[0])
        self.assertEqual(ctx.gallery_mosaic_cells, (urls[1], None, None, None))
        self.assertFalse(ctx.gallery_strip_extra)
        self.assertEqual(json.loads(ctx.gallery_images_json), list(urls))

    def test_without_prefetch_cache_returns_empty_urls(self):
        listing = self._published_listing("Sin prefetch")
        urls = ordered_listing_image_urls(listing)
        self.assertEqual(urls, ())

    def test_listing_detail_uses_first_gallery_image_for_social_meta(self):
        listing = self._published_listing("Con og")
        up = SimpleUploadedFile("a.png", _PNG_1X1, content_type="image/png")
        ListingImage.objects.create(listing=listing, image=up, sort_order=0)

        response = self.client.get(listing.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("/media/", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('property="og:image:type" content="image/png"', html)
        self.assertNotIn("AnunciateYa_ShareImage_Home.png", html)
