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
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
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

        # Autos
        v_listing = pub_listing("Auto test", "autos")
        VehicleListing.objects.create(
            listing=v_listing,
            brand="Seed",
            model="S1",
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
        MotorcycleListing.objects.create(
            listing=m_listing,
            brand="M",
            model="Z",
            year=2019,
            mileage=5000,
            engine_cc=150,
            transmission=MotorcycleListing.Transmission.MANUAL,
            fuel_type=MotorcycleListing.FuelType.GASOLINA,
            condition=ItemCondition.USADO,
        )
        # Electrónica
        e_listing = pub_listing("Phone test", "electronica")
        ElectronicsListing.objects.create(
            listing=e_listing,
            brand="Acme",
            model="Z1",
            condition=ItemCondition.NUEVO,
            warranty=False,
            warranty_months=None,
        )
        # Hogar
        h_listing = pub_listing("Silla test", "hogar")
        HomeGoodsListing.objects.create(
            listing=h_listing,
            item_type=HomeItemType.FURNITURE,
            condition=ItemCondition.USADO,
            brand="Wood",
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
