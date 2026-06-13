from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.listings.forms import PropertyListingForm
from apps.listings.location_geocoding import (
    MAPBOX_PROVIDER,
    coordinates_within_ecuador,
    ecuador_bbox_querystring,
)
from apps.listings.models import Listing, MarketZone, PropertyListing


class LocationGeocodingHelpersTests(SimpleTestCase):
    def test_ecuador_bbox_querystring_format(self):
        self.assertEqual(
            ecuador_bbox_querystring(),
            "-92.008,-5.015,-75.233,1.442",
        )

    def test_coordinates_within_ecuador_accepts_guayaquil(self):
        self.assertTrue(
            coordinates_within_ecuador(
                Decimal("-2.189400"),
                Decimal("-79.889100"),
            )
        )

    def test_coordinates_within_ecuador_rejects_outside(self):
        self.assertFalse(
            coordinates_within_ecuador(
                Decimal("40.712800"),
                Decimal("-74.006000"),
            )
        )


class ListingPublicLocationTests(TestCase):
    def setUp(self):
        from apps.categories.models import Category
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email="seller@example.com",
            password="pass12345",
        )
        self.category = Category.objects.create(name="Inmuebles", slug="inmuebles")
        self.zone, _ = MarketZone.objects.get_or_create(
            slug="kennedy-test-location",
            defaults={
                "name": "Kennedy Test Location",
                "city": "Guayaquil",
                "is_active": True,
            },
        )
        self.listing = Listing.objects.create(
            title="Casa test",
            description="Desc",
            price_amount="100000",
            currency="USD",
            zone=self.zone,
            location_reference="frente al kiosco",
            seller=self.user,
            category=self.category,
            status=Listing.Status.PUBLISHED,
        )

    def test_public_location_excludes_reference(self):
        self.assertEqual(self.listing.public_location, self.zone.name)
        self.assertEqual(self.listing.location, self.zone.name)
        self.assertNotIn("kiosco", self.listing.location)

    def test_location_with_reference_includes_both_for_admin(self):
        self.assertIn(self.zone.name, self.listing.location_with_reference)
        self.assertIn("kiosco", self.listing.location_with_reference)


class PropertyListingFormGeocodingTests(TestCase):
    def test_rejects_coordinates_outside_ecuador(self):
        form = PropertyListingForm(
            data={
                "property_type": "casa",
                "operation_type": "",
                "rooms": "3",
                "bathrooms": "2",
                "area_m2": "120",
                "parking_spaces": "",
                "furnished": "",
                "property_condition": "",
                "address_line": "Calle remota",
                "address_place_label": "",
                "location_precision": "exact",
                "latitude": "40.712800",
                "longitude": "-74.006000",
                "geocoding_provider": MAPBOX_PROVIDER,
                "geocoding_place_id": "place.test",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)

    def test_accepts_mapbox_coordinates_inside_ecuador(self):
        form = PropertyListingForm(
            data={
                "property_type": "casa",
                "operation_type": "",
                "rooms": "3",
                "bathrooms": "2",
                "area_m2": "120",
                "parking_spaces": "",
                "furnished": "",
                "property_condition": "",
                "address_line": "Av. Principal 123",
                "address_place_label": "",
                "location_precision": "exact",
                "latitude": "-2.189400",
                "longitude": "-79.889100",
                "geocoding_provider": MAPBOX_PROVIDER,
                "geocoding_place_id": "place.test",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_save_sets_geocoding_metadata_for_mapbox(self):
        form = PropertyListingForm(
            data={
                "property_type": "casa",
                "operation_type": "",
                "rooms": "3",
                "bathrooms": "2",
                "area_m2": "120",
                "parking_spaces": "",
                "furnished": "",
                "property_condition": "",
                "address_line": "Av. Principal 123",
                "address_place_label": "",
                "location_precision": "exact",
                "latitude": "-2.189400",
                "longitude": "-79.889100",
                "geocoding_provider": MAPBOX_PROVIDER,
                "geocoding_place_id": "place.test",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        self.assertEqual(prop.geocoding_provider, MAPBOX_PROVIDER)
        self.assertEqual(prop.geocoding_place_id, "place.test")
        self.assertIsNotNone(prop.geocoded_at)
        self.assertEqual(
            prop.location_precision,
            PropertyListing.LocationPrecision.EXACT,
        )
