from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from apps.listings.forms import HomeGoodsListingForm
from apps.listings.models import (
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
)
from apps.listings.services import (
    build_home_browse_heading,
    parse_home_filters,
)


def _brand(name: str) -> MarketBrand:
    return MarketBrand.objects.get(name=name)


def _model(brand: MarketBrand, item_type: str, name: str) -> MarketModel:
    return MarketModel.objects.get(
        brand=brand,
        category_slug="hogar",
        item_type=item_type,
        name=name,
    )


class HomeGoodsListingFormChoicesTests(TestCase):
    def test_home_item_types_include_guayaquil_market_options(self):
        form = HomeGoodsListingForm()
        item_type_values = {
            value for value, _label in form.fields["item_type"].choices
        }

        self.assertIn(HomeItemType.FURNITURE, item_type_values)
        self.assertIn(HomeItemType.APPLIANCES, item_type_values)
        self.assertIn(HomeItemType.DECOR, item_type_values)
        self.assertIn(HomeItemType.KITCHENWARE, item_type_values)
        self.assertIn(HomeItemType.MATTRESSES_BEDS, item_type_values)
        self.assertIn(HomeItemType.OUTDOOR_GARDEN, item_type_values)
        self.assertFalse(form.fields["brand_fk"].queryset.exists())

        furniture_form = HomeGoodsListingForm(data={"item_type": HomeItemType.FURNITURE})
        brand_values = set(
            furniture_form.fields["brand_fk"].queryset.values_list("name", flat=True)
        )
        self.assertIn("Colineal", brand_values)
        self.assertIn("Pycca", brand_values)

        appliance_form = HomeGoodsListingForm(data={"item_type": HomeItemType.APPLIANCES})
        appliance_brand_values = set(
            appliance_form.fields["brand_fk"].queryset.values_list("name", flat=True)
        )
        self.assertIn("Indurama", appliance_brand_values)
        self.assertIn("TCL", appliance_brand_values)

        mattress_form = HomeGoodsListingForm(
            data={"item_type": HomeItemType.MATTRESSES_BEDS}
        )
        mattress_brand_values = set(
            mattress_form.fields["brand_fk"].queryset.values_list("name", flat=True)
        )
        self.assertIn("Chaide", mattress_brand_values)

    def test_item_type_scopes_brand_and_model_choices(self):
        indurama = _brand("Indurama")
        appliance_form = HomeGoodsListingForm(
            data={
                "item_type": HomeItemType.APPLIANCES,
                "brand_fk": str(indurama.pk),
            }
        )
        appliance_brand_values = set(appliance_form.fields["brand_fk"].queryset.values_list("name", flat=True))
        appliance_model_values = set(appliance_form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Indurama", appliance_brand_values)
        self.assertIn("Mabe", appliance_brand_values)
        self.assertIn("TCL", appliance_brand_values)
        self.assertIn("RI-475 Quarzo", appliance_model_values)
        self.assertIn("Pamplona Quarzo", appliance_model_values)
        self.assertIn("MWI-20CR", appliance_model_values)
        self.assertNotIn("Chaide", appliance_brand_values)
        self.assertNotIn("Imperial", appliance_model_values)

        chaide = _brand("Chaide")
        mattress_form = HomeGoodsListingForm(
            data={
                "item_type": HomeItemType.MATTRESSES_BEDS,
                "brand_fk": str(chaide.pk),
            }
        )
        mattress_model_values = set(mattress_form.fields["model_fk"].queryset.values_list("name", flat=True))

        self.assertIn("Imperial", mattress_model_values)
        self.assertIn("Continental de Lujo", mattress_model_values)
        self.assertIn("Queen", mattress_model_values)
        self.assertNotIn("RI-475 Quarzo", mattress_model_values)

    def test_model_must_belong_to_selected_type_and_brand_when_provided(self):
        indurama = _brand("Indurama")
        wrong_model = _model(_brand("Chaide"), HomeItemType.MATTRESSES_BEDS, "Imperial")
        form = HomeGoodsListingForm(
            data={
                "item_type": HomeItemType.APPLIANCES,
                "brand_fk": str(indurama.pk),
                "model_fk": str(wrong_model.pk),
                "condition": ItemCondition.USADO,
                "material": "",
                "dimensions": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("model_fk", form.errors)

    def test_valid_market_selection_saves_brand_and_model_fk(self):
        brand = _brand("Indurama")
        model = _model(brand, HomeItemType.APPLIANCES, "RI-475 Quarzo")
        form = HomeGoodsListingForm(
            data={
                "item_type": HomeItemType.APPLIANCES,
                "brand_fk": str(brand.pk),
                "model_fk": str(model.pk),
                "condition": ItemCondition.USADO,
                "material": "",
                "dimensions": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        homegoods = form.save(commit=False)
        self.assertEqual(homegoods.item_type, HomeItemType.APPLIANCES)
        self.assertEqual(homegoods.brand_fk, brand)
        self.assertEqual(homegoods.model_fk, model)

    def test_blank_brand_and_model_remain_allowed_for_unbranded_home_items(self):
        form = HomeGoodsListingForm(
            data={
                "item_type": HomeItemType.DECOR,
                "brand_fk": "",
                "model_fk": "",
                "condition": ItemCondition.USADO,
                "material": "Cerámica",
                "dimensions": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_loads_fk_brand_and_model_values(self):
        brand = _brand("Colineal")
        model = _model(brand, HomeItemType.FURNITURE, "Sofá 3 puestos")
        extension = HomeGoodsListing(
            listing=Listing(title="Legacy"),
            item_type=HomeItemType.FURNITURE,
            brand_fk=brand,
            model_fk=model,
            condition=ItemCondition.USADO,
        )
        extension.pk = 1

        form = HomeGoodsListingForm(instance=extension)

        self.assertIn(brand, form.fields["brand_fk"].queryset)
        self.assertIn(model, form.fields["model_fk"].queryset)

    def test_homegoods_model_options_endpoint_returns_brand_models(self):
        brand = _brand("Indurama")
        response = self.client.get(
            reverse("homegoods_model_options"),
            {
                "item_type": HomeItemType.APPLIANCES,
                "brand": str(brand.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RI-475 Quarzo")
        self.assertContains(response, "MWI-20CR")
        self.assertNotContains(response, "Imperial")
        self.assertContains(response, "Otro")

    def test_homegoods_brand_options_endpoint_returns_type_brands(self):
        response = self.client.get(
            reverse("homegoods_brand_options"),
            {"item_type": HomeItemType.MATTRESSES_BEDS},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chaide")
        self.assertContains(response, "Paraíso")
        self.assertNotContains(response, "Indurama")

    def test_homegoods_brand_options_endpoint_requires_type(self):
        response = self.client.get(reverse("homegoods_brand_options"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Primero selecciona tipo")
        self.assertNotContains(response, "Indurama")


class HomeGoodsBrowseSeoTests(TestCase):
    def test_filter_parser_accepts_brand_and_model(self):
        brand = _brand("Indurama")
        model = _model(brand, HomeItemType.APPLIANCES, "RI-475 Quarzo")
        parsed = parse_home_filters(
            QueryDict(
                f"item_type=appliances&brand={brand.pk}&model={model.pk}&condition=usado&price_from=100&price_to=900"
            )
        )

        self.assertEqual(parsed["item_type"], HomeItemType.APPLIANCES)
        self.assertEqual(parsed["brand"], "Indurama")
        self.assertEqual(parsed["model"], "RI-475 Quarzo")
        self.assertEqual(parsed["condition"], ItemCondition.USADO)

    def test_home_heading_uses_type_brand_model_condition_and_city(self):
        heading = build_home_browse_heading(
            city="Guayaquil",
            parsed={
                "item_type": HomeItemType.APPLIANCES,
                "brand": "Indurama",
                "model": "RI-475 Quarzo",
                "condition": ItemCondition.USADO,
                "price_from": None,
                "price_to": None,
            },
        )

        self.assertEqual(
            heading,
            "Hogar electrodomésticos / cocina Indurama RI-475 Quarzo usado / usada en Guayaquil",
        )
