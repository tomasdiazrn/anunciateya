from django.test import SimpleTestCase, TestCase

from apps.listings.forms import PropertyListingForm
from apps.listings.models import PropertyListing
from apps.listings.services import (
    build_property_browse_heading,
    parse_property_list_filter_params,
)
from django.http import QueryDict


class PropertyListingFormChoicesTests(TestCase):
    def test_market_property_type_choices_include_ecuador_portal_options(self):
        form = PropertyListingForm()
        property_type_values = {
            value for value, _label in form.fields["property_type"].choices
        }

        self.assertIn(PropertyListing.PropertyType.CASA, property_type_values)
        self.assertIn(PropertyListing.PropertyType.DEPARTAMENTO, property_type_values)
        self.assertIn(PropertyListing.PropertyType.SUITE, property_type_values)
        self.assertIn(PropertyListing.PropertyType.TERRENO_LOTE, property_type_values)
        self.assertIn(
            PropertyListing.PropertyType.OFICINA_COMERCIAL,
            property_type_values,
        )
        self.assertIn(
            PropertyListing.PropertyType.LOCAL_COMERCIAL,
            property_type_values,
        )
        self.assertIn(PropertyListing.PropertyType.BODEGA_GALPON, property_type_values)
        self.assertIn(
            PropertyListing.PropertyType.HACIENDA_QUINTA,
            property_type_values,
        )
        self.assertIn(PropertyListing.PropertyType.HABITACION, property_type_values)

    def test_operation_type_choices_include_market_operations(self):
        form = PropertyListingForm()
        operation_values = {
            value for value, _label in form.fields["operation_type"].choices
        }

        self.assertIn(PropertyListing.OperationType.VENTA, operation_values)
        self.assertIn(PropertyListing.OperationType.ALQUILER, operation_values)
        self.assertIn(
            PropertyListing.OperationType.ALQUILER_TEMPORAL,
            operation_values,
        )


class PropertyListFilterParserTests(SimpleTestCase):
    def test_parser_accepts_expanded_market_values(self):
        params = parse_property_list_filter_params(
            QueryDict(
                "tipo=local_comercial&operacion=alquiler_temporal&rooms=2&bathrooms=1"
            )
        )

        self.assertEqual(
            params["property_type"],
            PropertyListing.PropertyType.LOCAL_COMERCIAL,
        )
        self.assertEqual(
            params["operation_type"],
            PropertyListing.OperationType.ALQUILER_TEMPORAL,
        )
        self.assertEqual(params["rooms_min"], 2)
        self.assertEqual(params["bathrooms_min"], 1)

    def test_parser_rejects_unknown_values(self):
        params = parse_property_list_filter_params(
            QueryDict("tipo=castillo&operation=permuta")
        )

        self.assertIsNone(params["property_type"])
        self.assertIsNone(params["operation_type"])

    def test_parser_rejects_price_values_with_symbols_or_decimals(self):
        params = parse_property_list_filter_params(
            QueryDict("price_from=49.99&price_to=$150000")
        )

        self.assertIsNone(params["price_from"])
        self.assertIsNone(params["price_to"])


class PropertyBrowseSeoHeadingTests(SimpleTestCase):
    def test_heading_uses_plural_property_type_and_operation_labels(self):
        heading = build_property_browse_heading(
            city="Guayaquil",
            parsed={
                "property_type": PropertyListing.PropertyType.LOCAL_COMERCIAL,
                "operation_type": PropertyListing.OperationType.VENTA,
            },
        )

        self.assertEqual(heading, "Locales comerciales en venta en Guayaquil")

    def test_heading_supports_alquiler_temporal(self):
        heading = build_property_browse_heading(
            city="Guayaquil",
            parsed={
                "property_type": PropertyListing.PropertyType.SUITE,
                "operation_type": PropertyListing.OperationType.ALQUILER_TEMPORAL,
            },
        )

        self.assertEqual(heading, "Suites en alquiler temporal en Guayaquil")
