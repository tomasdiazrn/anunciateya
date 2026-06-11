from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from apps.listings.forms import ElectronicsListingForm
from apps.listings.models import (
    ElectronicsItemType,
    ElectronicsListing,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
)
from apps.listings.services import (
    build_electronics_browse_heading,
    parse_electronics_list_filter_params,
)


def _brand(name: str) -> MarketBrand:
    return MarketBrand.objects.get(name=name)


def _model(brand: MarketBrand, item_type: str, name: str) -> MarketModel:
    return MarketModel.objects.get(
        brand=brand,
        category_slug="electronica",
        item_type=item_type,
        name=name,
    )


class ElectronicsListingFormChoicesTests(TestCase):
    def test_market_brand_and_model_choices_include_ecuador_top_options(self):
        form = ElectronicsListingForm()
        item_type_values = {
            value for value, _label in form.fields["item_type"].choices
        }

        self.assertIn(ElectronicsItemType.CELULARES, item_type_values)
        self.assertIn(ElectronicsItemType.LAPTOPS_COMPUTADORAS, item_type_values)
        self.assertIn(ElectronicsItemType.TV_AUDIO_VIDEO, item_type_values)
        self.assertIn(ElectronicsItemType.CONSOLAS_VIDEOJUEGOS, item_type_values)
        self.assertIn(ElectronicsItemType.REDES_ACCESORIOS, item_type_values)
        self.assertFalse(form.fields["brand_fk"].queryset.exists())

        phone_form = ElectronicsListingForm(
            data={"item_type": ElectronicsItemType.CELULARES}
        )
        brand_values = set(
            phone_form.fields["brand_fk"].queryset.values_list("name", flat=True)
        )
        self.assertIn("Apple", brand_values)
        self.assertIn("Samsung", brand_values)
        self.assertIn("Xiaomi", brand_values)
        self.assertIn("Honor", brand_values)
        self.assertIn("Huawei", brand_values)

        samsung = _brand("Samsung")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(samsung.pk),
            }
        )
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Galaxy A16", model_values)
        self.assertIn("Galaxy A56", model_values)
        self.assertIn("Galaxy S25 Ultra", model_values)
        self.assertIn("Otro", model_values)

        apple = _brand("Apple")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(apple.pk),
            }
        )
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("iPhone 13 Pro", model_values)
        self.assertIn("iPhone 16 Pro Max", model_values)

        xiaomi = _brand("Xiaomi")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(xiaomi.pk),
            }
        )
        model_values = set(form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Redmi Note 15", model_values)

    def test_item_type_scopes_brand_and_model_choices(self):
        samsung = _brand("Samsung")
        phone_form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(samsung.pk),
            }
        )
        phone_brand_values = set(phone_form.fields["brand_fk"].queryset.values_list("name", flat=True))
        phone_model_values = set(phone_form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Samsung", phone_brand_values)
        self.assertIn("Galaxy A16", phone_model_values)
        self.assertNotIn("HP", phone_brand_values)
        self.assertNotIn("Smart TV 70", phone_model_values)

        tv_form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.TV_AUDIO_VIDEO,
                "brand_fk": str(samsung.pk),
            }
        )
        tv_model_values = set(tv_form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Smart TV 55", tv_model_values)
        self.assertIn("QLED 65", tv_model_values)
        self.assertNotIn("Galaxy A16", tv_model_values)

    def test_model_must_belong_to_selected_brand(self):
        samsung = _brand("Samsung")
        wrong_model = _model(_brand("Apple"), ElectronicsItemType.CELULARES, "iPhone 13 Pro")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(samsung.pk),
                "model_fk": str(wrong_model.pk),
                "condition": ItemCondition.USADO,
                "warranty": "",
                "warranty_months": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("model_fk", form.errors)

    def test_model_must_belong_to_selected_type_and_brand(self):
        samsung = _brand("Samsung")
        wrong_model = _model(samsung, ElectronicsItemType.TV_AUDIO_VIDEO, "Smart TV 55")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(samsung.pk),
                "model_fk": str(wrong_model.pk),
                "condition": ItemCondition.USADO,
                "warranty": "",
                "warranty_months": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("model_fk", form.errors)

    def test_new_listing_rejects_arbitrary_brand_post(self):
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": "",
                "model_fk": "",
                "condition": ItemCondition.USADO,
                "warranty": "",
                "warranty_months": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("brand_fk", form.errors)

    def test_valid_market_selection_saves_brand_and_model_fk(self):
        brand = _brand("Xiaomi")
        model = _model(brand, ElectronicsItemType.CELULARES, "Redmi Note 13")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(brand.pk),
                "model_fk": str(model.pk),
                "condition": ItemCondition.USADO,
                "warranty": "",
                "warranty_months": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        electronics = form.save(commit=False)
        self.assertEqual(electronics.brand_fk, brand)
        self.assertEqual(electronics.model_fk, model)
        self.assertEqual(electronics.item_type, ElectronicsItemType.CELULARES)

    def test_valid_market_brand_allows_other_model(self):
        brand = _brand("Apple")
        model = _model(brand, ElectronicsItemType.CELULARES, "Otro")
        form = ElectronicsListingForm(
            data={
                "item_type": ElectronicsItemType.CELULARES,
                "brand_fk": str(brand.pk),
                "model_fk": str(model.pk),
                "condition": ItemCondition.USADO,
                "warranty": "",
                "warranty_months": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        electronics = form.save(commit=False)
        self.assertEqual(electronics.brand_fk, brand)
        self.assertEqual(electronics.model_fk, model)

    def test_edit_loads_fk_brand_and_model_values(self):
        brand = _brand("Apple")
        model = _model(brand, ElectronicsItemType.CELULARES, "iPhone 13 Pro")
        extension = ElectronicsListing(
            listing=Listing(title="Legacy"),
            brand_fk=brand,
            model_fk=model,
            item_type=ElectronicsItemType.CELULARES,
            condition=ItemCondition.USADO,
        )
        extension.pk = 1

        form = ElectronicsListingForm(instance=extension)

        self.assertIn(brand, form.fields["brand_fk"].queryset)
        self.assertIn(model, form.fields["model_fk"].queryset)

    def test_electronics_model_options_endpoint_returns_brand_models(self):
        samsung = _brand("Samsung")
        response = self.client.get(
            reverse("electronics_model_options"),
            {
                "item_type": ElectronicsItemType.TV_AUDIO_VIDEO,
                "brand": str(samsung.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Galaxy A16")
        self.assertContains(response, "Smart TV 70")
        self.assertContains(response, "QLED 65")
        self.assertContains(response, "Otro")

    def test_electronics_brand_options_endpoint_returns_type_brands(self):
        response = self.client.get(
            reverse("electronics_brand_options"),
            {"item_type": ElectronicsItemType.CELULARES},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samsung")
        self.assertContains(response, "Apple")
        self.assertNotContains(response, "HP")

    def test_electronics_brand_options_endpoint_requires_type(self):
        response = self.client.get(reverse("electronics_brand_options"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Primero selecciona tipo")
        self.assertNotContains(response, "Samsung")


class ElectronicsBrowseSeoTests(TestCase):
    def test_filter_parser_accepts_item_type(self):
        brand = _brand("Apple")
        parsed = parse_electronics_list_filter_params(
            QueryDict(
                f"item_type=celulares&brand={brand.pk}&condition=usado&warranty=1&price_from=100&price_to=900"
            )
        )

        self.assertEqual(parsed["item_type"], ElectronicsItemType.CELULARES)
        self.assertEqual(parsed["brand"], "Apple")
        self.assertEqual(parsed["condition"], ItemCondition.USADO)
        self.assertIs(parsed["warranty"], True)

    def test_filter_parser_rejects_unknown_item_type(self):
        parsed = parse_electronics_list_filter_params(
            QueryDict("item_type=lavadoras&condition=usado")
        )

        self.assertIsNone(parsed["item_type"])
        self.assertEqual(parsed["condition"], ItemCondition.USADO)

    def test_electronics_heading_uses_type_brand_condition_and_city(self):
        heading = build_electronics_browse_heading(
            city="Guayaquil",
            parsed={
                "item_type": ElectronicsItemType.CELULARES,
                "brand": "Apple",
                "condition": ItemCondition.USADO,
                "warranty": True,
                "price_from": None,
                "price_to": None,
            },
        )

        self.assertEqual(heading, "Celulares Apple usados con garantía en Guayaquil")
