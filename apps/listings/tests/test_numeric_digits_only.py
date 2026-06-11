from django.http import QueryDict
from django.test import SimpleTestCase

from apps.listings.forms import BaseListingForm, PropertyListingForm
from apps.listings.models import Listing, PropertyListing
from apps.listings.services import (
    parse_property_list_filter_params,
    parse_vehicle_list_filter_params,
)


class ListingNumericDigitsOnlyTests(SimpleTestCase):
    def test_listing_price_rejects_decimal_symbol(self):
        form = BaseListingForm(
            data={
                "title": "Anuncio",
                "description": "Detalle suficiente",
                "price_amount": "120.50",
                "currency": "USD",
                "location": "Guayaquil",
                "publish_state": Listing.Status.PUBLISHED,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("price_amount", form.errors)

    def test_property_numeric_fields_reject_symbols(self):
        form = PropertyListingForm(
            data={
                "property_type": PropertyListing.PropertyType.CASA,
                "operation_type": "",
                "rooms": "+3",
                "bathrooms": "2",
                "area_m2": "120",
                "parking_spaces": "1",
                "furnished": "",
                "property_condition": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("rooms", form.errors)

    def test_vehicle_filter_parser_ignores_non_digit_numbers(self):
        params = QueryDict(
            "year_from=%2B2015&year_to=2024&price_from=10.50&price_to=9000"
        )

        parsed = parse_vehicle_list_filter_params(params)

        self.assertIsNone(parsed["year_from"])
        self.assertEqual(parsed["year_to"], 2024)
        self.assertIsNone(parsed["price_from"])
        self.assertEqual(parsed["price_to"], 9000)

    def test_property_filter_parser_ignores_non_digit_numbers(self):
        params = QueryDict("rooms=1e2&bathrooms=2&price_from=$500&price_to=900")

        parsed = parse_property_list_filter_params(params)

        self.assertIsNone(parsed["rooms_min"])
        self.assertEqual(parsed["bathrooms_min"], 2)
        self.assertIsNone(parsed["price_from"])
        self.assertEqual(parsed["price_to"], 900)
