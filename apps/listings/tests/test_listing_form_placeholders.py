from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.categories.models import Category
from apps.listings.category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from apps.listings.forms import (
    BaseListingForm,
    ElectronicsListingForm,
    HomeGoodsListingForm,
    MotorcycleListingForm,
    PropertyListingForm,
    VehicleListingForm,
)
from apps.listings.models import Listing, MarketZone

User = get_user_model()


class ListingFormPlaceholderTests(TestCase):
    def test_title_placeholders_follow_publish_category(self):
        cases = {
            VEHICLE_SLUG: "Toyota Corolla",
            PROPERTY_SLUG: "Casa 3 habitaciones",
            MOTORCYCLE_SLUG: "Honda CB",
            ELECTRONICS_SLUG: "iPhone 13 Pro",
            HOMEGOODS_SLUG: "Sofá de 3 cuerpos",
            "servicios": "Artículo en buen estado",
        }

        for slug, expected in cases.items():
            with self.subTest(slug=slug):
                form = BaseListingForm(category_slug=slug)

                self.assertIn(
                    expected,
                    form.fields["title"].widget.attrs["placeholder"],
                )

    def test_edit_form_uses_listing_category_placeholder(self):
        seller = User.objects.create_user(
            email="placeholder-seller@example.com",
            password="test-pass-123",
        )
        category = Category.objects.create(name="Hogar", slug=HOMEGOODS_SLUG)
        zone = MarketZone.objects.get(slug="otro-guayaquil")
        listing = Listing.objects.create(
            title="Mesa usada",
            description="Mesa en buen estado.",
            price_amount="80.00",
            currency="USD",
            zone=zone,
            seller=seller,
            category=category,
            status=Listing.Status.PUBLISHED,
        )

        form = BaseListingForm(instance=listing)

        self.assertIn(
            "Sofá de 3 cuerpos",
            form.fields["title"].widget.attrs["placeholder"],
        )

    def test_price_amount_accepts_digits_only(self):
        base_data = {
            "title": "Mesa usada",
            "description": "Mesa en buen estado.",
            "currency": "USD",
            "zone": MarketZone.objects.get(slug="otro-guayaquil").pk,
            "location_reference": "",
            "publish_state": Listing.Status.PUBLISHED,
        }

        decimal_form = BaseListingForm(data={**base_data, "price_amount": "49.99"})
        symbol_form = BaseListingForm(data={**base_data, "price_amount": "$4999"})

        self.assertFalse(decimal_form.is_valid())
        self.assertIn("price_amount", decimal_form.errors)
        self.assertFalse(symbol_form.is_valid())
        self.assertIn("price_amount", symbol_form.errors)

    def test_category_selects_use_clear_empty_labels(self):
        cases = [
            (
                PropertyListingForm,
                {
                    "property_type": "Selecciona el tipo de propiedad",
                    "operation_type": "Selecciona la operación",
                    "property_condition": "Selecciona el estado del inmueble",
                },
            ),
            (
                VehicleListingForm,
                {"model_fk": "Primero selecciona una marca"},
            ),
            (
                MotorcycleListingForm,
                {
                    "model_fk": "Primero selecciona una marca",
                    "condition": "Selecciona la condición",
                },
            ),
            (
                ElectronicsListingForm,
                {
                    "item_type": "Selecciona el tipo de producto",
                    "brand_fk": "Primero selecciona el tipo de producto",
                    "model_fk": "Primero selecciona una marca",
                    "condition": "Selecciona la condición",
                },
            ),
            (
                HomeGoodsListingForm,
                {
                    "item_type": "Selecciona el tipo de artículo",
                    "brand_fk": "Primero selecciona el tipo de artículo",
                    "model_fk": "Primero selecciona una marca",
                    "condition": "Selecciona la condición",
                },
            ),
        ]

        for form_class, expected_labels in cases:
            form = form_class()
            for field_name, expected_label in expected_labels.items():
                with self.subTest(form=form_class.__name__, field=field_name):
                    empty_value, empty_label = list(form.fields[field_name].choices)[0]

                    self.assertEqual(empty_value, "")
                    self.assertEqual(empty_label, expected_label)
                    self.assertNotIn("-", empty_label)

    def test_location_toggle_off_clears_zone(self):
        zone = MarketZone.objects.get(slug="otro-guayaquil")
        form = BaseListingForm(
            data={
                "title": "Mesa usada",
                "description": "Mesa en buen estado.",
                "price_amount": "49",
                "currency": "USD",
                "zone": zone.pk,
                "location_reference": "frente al parque",
                "publish_state": Listing.Status.PUBLISHED,
                "add_location_present": "1",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["zone"])
        self.assertEqual(form.cleaned_data["location_reference"], "")

    def test_location_toggle_on_requires_zone(self):
        form = BaseListingForm(
            data={
                "title": "Mesa usada",
                "description": "Mesa en buen estado.",
                "price_amount": "49",
                "currency": "USD",
                "zone": "",
                "location_reference": "",
                "publish_state": Listing.Status.PUBLISHED,
                "add_location": "on",
                "add_location_present": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("zone", form.errors)

    def test_property_coordinates_must_be_complete_pair(self):
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
                "longitude": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("longitude", form.errors)

    def test_property_exact_location_valid_without_coordinates(self):
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
                "address_place_label": "Edificio Norte",
                "location_precision": "exact",
                "latitude": "",
                "longitude": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_property_address_becomes_exact_location(self):
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
                "latitude": "",
                "longitude": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["location_precision"],
            "exact",
        )
