"""Contrato del Category Engine: DTO de cards, SEO y presupuesto de queries."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.categories.models import Category
from apps.listings.category_engine import build_category_page, build_category_seo_context
from apps.listings.category_engine_validation import EXPECTED_CONTRACT_SLUGS
from apps.listings.listing_card_dto import LISTING_CARD_DTO_UNIFIED, CardContext, build_card_context
from apps.listings.models import (
    ElectronicsListing,
    ElectronicsItemType,
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)

User = get_user_model()

_MAX_BADGES = 5
_MAX_ATTRIBUTES = 5

# Techo holgado para CI / SQLite; el objetivo es detectar regresiones grandes (N+1).
_QUERY_CEILING_BY_PATH = {
    "/autos/": 35,
    "/motos/": 35,
    "/inmuebles/": 35,
    "/electronica/": 35,
    "/hogar/": 35,
}


class CategoryEngineContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="contract_seller@example.com",
            password="test-pass-123",
        )
        cats: dict[str, Category] = {}
        for order, slug in enumerate(sorted(EXPECTED_CONTRACT_SLUGS)):
            name = slug.title()
            c, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "order": order},
            )
            cats[slug] = c

        def pub_listing(title: str, slug: str) -> Listing:
            cat = cats[slug]
            l = Listing.objects.create(
                title=title,
                description="d",
                price_amount="1000.00",
                currency="USD",
                location="Guayaquil",
                seller=cls.seller,
                category=cat,
                status=Listing.Status.PUBLISHED,
            )
            return l

        def market_model(
            brand_name: str,
            model_name: str,
            category_slug: str,
            item_type: str = "",
        ) -> tuple[MarketBrand, MarketModel]:
            brand, _ = MarketBrand.objects.get_or_create(
                name=brand_name,
                defaults={"slug": f"{brand_name.lower()}-{category_slug}", "is_active": True},
            )
            model, _ = MarketModel.objects.get_or_create(
                brand=brand,
                category_slug=category_slug,
                item_type=item_type,
                name=model_name,
                defaults={"slug": f"{model_name.lower()}-{category_slug}", "is_active": True},
            )
            return brand, model

        # Autos
        v_listing = pub_listing("Auto test", "autos")
        v_brand, v_model = market_model("Seed", "S1", "autos")
        VehicleListing.objects.create(
            listing=v_listing,
            brand_fk=v_brand,
            model_fk=v_model,
            year=2020,
            doors=4,
            mileage=10000,
            transmission=VehicleListing.Transmission.MANUAL,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )
        # Inmuebles
        p_listing = pub_listing("Casa test", "inmuebles")
        PropertyListing.objects.create(
            listing=p_listing,
            property_type=PropertyListing.PropertyType.CASA,
            operation_type=PropertyListing.OperationType.VENTA,
            rooms=3,
            bathrooms=2,
            area_m2=120,
            parking_spaces=1,
            furnished=False,
            property_condition=PropertyListing.PropertyConditionChoice.USADO,
        )
        # Motos
        m_listing = pub_listing("Moto test", "motos")
        m_brand, m_model = market_model("M", "Z", "motos")
        MotorcycleListing.objects.create(
            listing=m_listing,
            brand_fk=m_brand,
            model_fk=m_model,
            year=2019,
            mileage=5000,
            engine_cc=150,
            transmission=MotorcycleListing.Transmission.MANUAL,
            fuel_type=MotorcycleListing.FuelType.GASOLINA,
            condition=ItemCondition.USADO,
        )
        # Electrónica
        e_listing = pub_listing("Phone test", "electronica")
        e_brand, e_model = market_model(
            "Acme",
            "Z1",
            "electronica",
            ElectronicsItemType.CELULARES,
        )
        ElectronicsListing.objects.create(
            listing=e_listing,
            item_type=ElectronicsItemType.CELULARES,
            brand_fk=e_brand,
            model_fk=e_model,
            condition=ItemCondition.NUEVO,
            warranty=False,
            warranty_months=None,
        )
        # Hogar
        h_listing = pub_listing("Silla test", "hogar")
        h_brand, h_model = market_model("Wood", "Silla", "hogar", HomeItemType.FURNITURE)
        HomeGoodsListing.objects.create(
            listing=h_listing,
            item_type=HomeItemType.FURNITURE,
            condition=ItemCondition.USADO,
            brand_fk=h_brand,
            model_fk=h_model,
            material="Pino",
        )

        cls.listings_by_slug = {
            "autos": v_listing,
            "inmuebles": p_listing,
            "motos": m_listing,
            "electronica": e_listing,
            "hogar": h_listing,
        }

    def test_card_templates_do_not_reference_listing_object(self) -> None:
        root = Path(settings.BASE_DIR) / "templates" / "components" / "marketplace" / "cards"
        for path in sorted(root.glob("*.html")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "listing.",
                text,
                f"{path.name} no debe acceder a listing.* (solo CardContext).",
            )

    def test_build_card_context_per_registry_slug(self) -> None:
        for slug in sorted(EXPECTED_CONTRACT_SLUGS):
            listing = self.listings_by_slug[slug]
            card = build_card_context(listing, slug, trust_map={})
            self.assertIsInstance(card, CardContext)
            self.assertEqual(card.template, LISTING_CARD_DTO_UNIFIED)
            self.assertTrue(card.link.startswith("/"))
            self.assertLessEqual(len(card.badges), _MAX_BADGES)
            self.assertLessEqual(len(card.attributes), _MAX_ATTRIBUTES)
            self.assertIsInstance(card.price_display, str)
            self.assertTrue(card.price_display)
            self.assertIsNotNone(card.seo_text)
            self.assertTrue(card.category_label)
            self.assertTrue(card.category_href.startswith("/"))
            self.assertIsInstance(card.is_featured, bool)
            self.assertIsInstance(card.is_featured_top, bool)
            self.assertIsInstance(card.is_promoted_featured, bool)
            self.assertIsInstance(card.is_promoted_boost, bool)
            self.assertFalse(card.is_promoted_featured)
            self.assertFalse(card.is_promoted_boost)
            self.assertEqual(card.listing_id, listing.pk)
            self.assertIsInstance(card.publisher_label, str)

    def test_category_hub_seo_bundle_canonical_absolute(self) -> None:
        rf = RequestFactory()
        for slug in sorted(EXPECTED_CONTRACT_SLUGS):
            req = rf.get(f"/{slug}/")
            page = build_category_page(req, category_slug=slug)
            href = page.seo.canonical_href
            self.assertIsNotNone(href)
            self.assertTrue(
                href.startswith("http://") or href.startswith("https://"),
                f"{slug}: canonical debe ser absoluta, obtuvo {href!r}",
            )

    def test_build_category_seo_context_canonical_absolute(self) -> None:
        rf = RequestFactory()
        req = rf.get("/autos/")
        cat = Category.objects.get(slug="autos")
        qs = Listing.objects.published().filter(category=cat)
        bundle = build_category_seo_context(
            req,
            "autos",
            qs,
            frame="hub",
            brand="T",
            city="G",
            category=cat,
            parsed={},
            result_count=0,
            q_raw="",
            filters_active=False,
        )
        self.assertTrue(bundle.canonical_href.startswith("http"))

    @override_settings(DEBUG=True)
    def test_category_hub_query_budget(self) -> None:
        c = Client()
        for path, ceiling in _QUERY_CEILING_BY_PATH.items():
            with CaptureQueriesContext(connection) as ctx:
                r = c.get(path)
            self.assertEqual(r.status_code, 200)
            n = len(ctx.captured_queries)
            self.assertLessEqual(
                n,
                ceiling,
                f"{path}: {n} queries (techo {ceiling}); posible regresión N+1.",
            )
