"""Presupuesto de queries del browse (/anuncios/) vía QueryPlan centralizado."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings

from apps.categories.models import Category
from django.test.utils import CaptureQueriesContext

from apps.listings.category_engine import build_browse_listings_queryset
from apps.listings.category_extensions import MOTORCYCLE_SLUG, PROPERTY_SLUG, VEHICLE_SLUG
from apps.listings.category_engine_queryplan import browse_listings_query_plan
from apps.listings.models import (
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
    MarketZone,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)

User = get_user_model()


class BrowseQueryPlanQueryBudgetTests(TestCase):
    """Evalúa solo el fetch de la primera página (sin COUNT ni sidebar SEO)."""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="qp_seller@example.com",
            password="x",
        )
        cls.cat_autos, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        cls.cat_inm, _ = Category.objects.get_or_create(
            slug=PROPERTY_SLUG,
            defaults={"name": "Inmuebles", "order": 1},
        )
        cls.cat_motos, _ = Category.objects.get_or_create(
            slug=MOTORCYCLE_SLUG,
            defaults={"name": "Motos", "order": 2},
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

        def market_model(brand_name: str, model_name: str, category_slug: str):
            brand, _ = MarketBrand.objects.get_or_create(
                name=brand_name,
                defaults={"slug": f"{brand_name.lower()}-{category_slug}", "is_active": True},
            )
            model, _ = MarketModel.objects.get_or_create(
                brand=brand,
                category_slug=category_slug,
                item_type="",
                name=model_name,
                defaults={"slug": f"{model_name.lower()}-{category_slug}", "is_active": True},
            )
            return brand, model

        la = Listing.objects.create(
            title="A1",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=cls.zone,
            seller=cls.seller,
            category=cls.cat_autos,
            status=Listing.Status.PUBLISHED,
        )
        v_brand, v_model = market_model("B", "M", VEHICLE_SLUG)
        VehicleListing.objects.create(
            listing=la,
            brand_fk=v_brand,
            model_fk=v_model,
            year=2020,
            doors=4,
            transmission=VehicleListing.Transmission.MANUAL,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )
        li = Listing.objects.create(
            title="I1",
            description="d",
            price_amount="2000",
            currency="USD",
            zone=cls.zone,
            seller=cls.seller,
            category=cls.cat_inm,
            status=Listing.Status.PUBLISHED,
        )
        PropertyListing.objects.create(
            listing=li,
            property_type=PropertyListing.PropertyType.CASA,
            operation_type=PropertyListing.OperationType.VENTA,
            rooms=2,
            bathrooms=1,
            area_m2=80,
        )
        lm = Listing.objects.create(
            title="M1",
            description="d",
            price_amount="500",
            currency="USD",
            zone=cls.zone,
            seller=cls.seller,
            category=cls.cat_motos,
            status=Listing.Status.PUBLISHED,
        )
        m_brand, m_model = market_model("MB", "MM", MOTORCYCLE_SLUG)
        MotorcycleListing.objects.create(
            listing=lm,
            brand_fk=m_brand,
            model_fk=m_model,
            year=2018,
            transmission=MotorcycleListing.Transmission.MANUAL,
            fuel_type=MotorcycleListing.FuelType.GASOLINA,
            condition=ItemCondition.USADO,
        )

    def _assert_fetch_first_page_under(
        self,
        *,
        category_slug: str,
        max_queries: int,
    ) -> None:
        rf = RequestFactory()
        request = rf.get("/anuncios/", {"category": category_slug})
        qs = build_browse_listings_queryset(request).filter(category__slug=category_slug)
        with CaptureQueriesContext(connection) as ctx:
            _ = list(qs[:12])
        n = len(ctx.captured_queries)
        self.assertLess(
            n,
            max_queries,
            f"category={category_slug!r}: {n} queries (máx {max_queries - 1}): {ctx.captured_queries!r}",
        )

    @override_settings(DEBUG=True)
    def test_browse_autos_list_fetch_under_3_queries(self) -> None:
        self._assert_fetch_first_page_under(category_slug=VEHICLE_SLUG, max_queries=3)

    @override_settings(DEBUG=True)
    def test_browse_motos_list_fetch_under_3_queries(self) -> None:
        self._assert_fetch_first_page_under(category_slug=MOTORCYCLE_SLUG, max_queries=3)

    @override_settings(DEBUG=True)
    def test_browse_inmuebles_list_fetch_under_3_queries(self) -> None:
        self._assert_fetch_first_page_under(category_slug=PROPERTY_SLUG, max_queries=3)

    def test_browse_query_plan_cached_on_request(self) -> None:
        rf = RequestFactory()
        request = rf.get("/anuncios/", {"category": VEHICLE_SLUG})
        p1 = browse_listings_query_plan(request)
        p2 = browse_listings_query_plan(request)
        self.assertIs(p1, p2)
        self.assertIn("_queryplan_cache", request.__dict__)
