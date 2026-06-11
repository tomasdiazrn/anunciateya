from django.test import TestCase
from django.urls import reverse

from apps.listings.forms import MotorcycleListingForm
from apps.listings.models import ItemCondition, MarketBrand, MarketModel, MotorcycleListing


def _brand(name: str) -> MarketBrand:
    return MarketBrand.objects.get(name=name)


def _model(brand: MarketBrand, name: str) -> MarketModel:
    return MarketModel.objects.get(
        brand=brand,
        category_slug="motos",
        item_type="",
        name=name,
    )


class MotorcycleListingFormChoicesTests(TestCase):
    def test_market_brand_and_model_choices_include_ecuador_top_options(self):
        form = MotorcycleListingForm()
        brand_values = set(form.fields["brand_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Shineray", brand_values)
        self.assertIn("Daytona", brand_values)
        self.assertIn("Bajaj", brand_values)
        self.assertIn("Suzuki", brand_values)
        self.assertIn("Thunder", brand_values)
        self.assertIn("KTM", brand_values)
        self.assertIn("TVS", brand_values)
        self.assertIn("Dukare", brand_values)
        self.assertIn("Husqvarna", brand_values)
        self.assertIn("Ducati", brand_values)

        shineray = _brand("Shineray")
        form = MotorcycleListingForm(data={"brand_fk": str(shineray.pk)})
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("XY150-15", model_values)
        self.assertIn("XY125-30A", model_values)
        self.assertIn("Jedi II", model_values)
        self.assertIn("Iron Max", model_values)
        self.assertIn("Freedom Music", model_values)
        self.assertIn("Otro", model_values)

        daytona = _brand("Daytona")
        form = MotorcycleListingForm(data={"brand_fk": str(daytona.pk)})
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("DY150 Workforce", model_values)
        self.assertIn("DY200 Wing Evo 2", model_values)

        tvs = _brand("TVS")
        form = MotorcycleListingForm(data={"brand_fk": str(tvs.pk)})
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Apache RTR 160", model_values)
        self.assertIn("Apache RR 310", model_values)

        ducati = _brand("Ducati")
        form = MotorcycleListingForm(data={"brand_fk": str(ducati.pk)})
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Multistrada 1200", model_values)
        self.assertIn("DesertX", model_values)

    def test_model_must_belong_to_selected_brand(self):
        shineray = _brand("Shineray")
        wrong_model = _model(_brand("Suzuki"), "GN125")
        form = MotorcycleListingForm(
            data={
                "brand_fk": str(shineray.pk),
                "model_fk": str(wrong_model.pk),
                "year": "2022",
                "transmission": MotorcycleListing.Transmission.MANUAL,
                "fuel_type": MotorcycleListing.FuelType.GASOLINA,
                "condition": ItemCondition.USADO,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("model_fk", form.errors)

    def test_new_listing_rejects_arbitrary_brand_post(self):
        form = MotorcycleListingForm(
            data={
                "brand": "Marca Inventada",
                "model": "Modelo Inventado",
                "year": "2022",
                "transmission": MotorcycleListing.Transmission.MANUAL,
                "fuel_type": MotorcycleListing.FuelType.GASOLINA,
                "condition": ItemCondition.USADO,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("brand_fk", form.errors)

    def test_valid_market_selection_saves_brand_and_model_fk(self):
        brand = _brand("Bajaj")
        model = _model(brand, "CT125")
        form = MotorcycleListingForm(
            data={
                "brand_fk": str(brand.pk),
                "model_fk": str(model.pk),
                "year": "2024",
                "engine_cc": "125",
                "mileage": "1000",
                "transmission": MotorcycleListing.Transmission.MANUAL,
                "fuel_type": MotorcycleListing.FuelType.GASOLINA,
                "condition": ItemCondition.USADO,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        motorcycle = form.save(commit=False)
        self.assertEqual(motorcycle.brand_fk, brand)
        self.assertEqual(motorcycle.model_fk, model)

    def test_valid_market_brand_allows_other_model(self):
        brand = _brand("Bajaj")
        model = _model(brand, "Otro")
        form = MotorcycleListingForm(
            data={
                "brand_fk": str(brand.pk),
                "model_fk": str(model.pk),
                "year": "2024",
                "engine_cc": "125",
                "mileage": "1000",
                "transmission": MotorcycleListing.Transmission.MANUAL,
                "fuel_type": MotorcycleListing.FuelType.GASOLINA,
                "condition": ItemCondition.USADO,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        motorcycle = form.save(commit=False)
        self.assertEqual(motorcycle.brand_fk, brand)
        self.assertEqual(motorcycle.model_fk, model)

    def test_motorcycle_model_options_endpoint_returns_brand_models(self):
        suzuki = _brand("Suzuki")
        response = self.client.get(
            reverse("motorcycle_model_options"),
            {"brand": str(suzuki.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GN125")
        self.assertContains(response, "GD115")
        self.assertContains(response, "GSX250R")
        self.assertContains(response, "V-Strom 1000")
        self.assertContains(response, "Otro")
