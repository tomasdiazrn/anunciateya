from django.test import TestCase
from django.urls import reverse

from apps.listings.forms import VehicleListingForm
from apps.listings.models import MarketBrand, MarketModel, VehicleListing


class VehicleListingFormChoicesTests(TestCase):
    def test_valid_vehicle_brand_allows_other_model(self):
        brand, _created = MarketBrand.objects.get_or_create(
            name="Toyota",
            defaults={"slug": "toyota", "is_active": True},
        )
        other_model, _created = MarketModel.objects.get_or_create(
            brand=brand,
            category_slug="autos",
            item_type="",
            name="Otro",
            defaults={"slug": "otro", "is_active": True},
        )

        form = VehicleListingForm(
            data={
                "brand_fk": str(brand.pk),
                "model_fk": str(other_model.pk),
                "year": "2024",
                "mileage": "1000",
                "doors": "4",
                "transmission": VehicleListing.Transmission.MANUAL,
                "fuel_type": VehicleListing.FuelType.GASOLINA,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        vehicle = form.save(commit=False)
        self.assertEqual(vehicle.brand_fk, brand)
        self.assertEqual(vehicle.model_fk, other_model)

    def test_vehicle_model_options_endpoint_returns_other_model(self):
        brand, _created = MarketBrand.objects.get_or_create(
            name="Chevrolet",
            defaults={"slug": "chevrolet", "is_active": True},
        )
        MarketModel.objects.get_or_create(
            brand=brand,
            category_slug="autos",
            item_type="",
            name="Aveo",
            defaults={"slug": "aveo", "is_active": True},
        )
        MarketModel.objects.get_or_create(
            brand=brand,
            category_slug="autos",
            item_type="",
            name="Otro",
            defaults={"slug": "otro", "is_active": True},
        )

        response = self.client.get(
            reverse("vehicle_model_options"),
            {"brand_fk": str(brand.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aveo")
        self.assertContains(response, "Otro")

    def test_vehicle_model_options_endpoint_accepts_browse_brand_param(self):
        brand, _created = MarketBrand.objects.get_or_create(
            name="Kia",
            defaults={"slug": "kia", "is_active": True},
        )
        MarketModel.objects.get_or_create(
            brand=brand,
            category_slug="autos",
            item_type="",
            name="Sportage",
            defaults={"slug": "sportage", "is_active": True},
        )

        response = self.client.get(
            reverse("vehicle_model_options"),
            {"brand": str(brand.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sportage")

    def test_vehicle_model_must_belong_to_active_auto_taxonomy(self):
        brand, _created = MarketBrand.objects.get_or_create(
            name="Toyota",
            defaults={"slug": "toyota", "is_active": True},
        )
        wrong_category_model = MarketModel.objects.create(
            brand=brand,
            category_slug="motos",
            item_type="",
            name="Otro",
            slug="otro-moto",
            is_active=True,
        )

        form = VehicleListingForm(
            data={
                "brand_fk": str(brand.pk),
                "model_fk": str(wrong_category_model.pk),
                "year": "2024",
                "mileage": "1000",
                "doors": "4",
                "transmission": VehicleListing.Transmission.MANUAL,
                "fuel_type": VehicleListing.FuelType.GASOLINA,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("model_fk", form.errors)
