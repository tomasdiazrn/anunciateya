"""Ranking global: featured, quality_score y orden estable."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.categories.models import Category
from apps.listings.category_engine import apply_category_pipeline
from apps.listings.category_extensions import VEHICLE_SLUG
from apps.listings.models import Listing, MarketBrand, MarketModel, MarketZone, VehicleListing
from apps.listings.services import compute_listing_quality_score

User = get_user_model()


class ListingRankingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="rank_seller@example.com",
            password="x",
        )
        cls.cat_autos, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

    def _vehicle_ext(self, listing: Listing) -> None:
        brand, model = self._market_model("B", "M")
        VehicleListing.objects.create(
            listing=listing,
            brand_fk=brand,
            model_fk=model,
            year=2020,
            doors=4,
            mileage=1000,
            transmission=VehicleListing.Transmission.MANUAL,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )

    def _market_model(self, brand_name: str, model_name: str):
        brand, _ = MarketBrand.objects.get_or_create(
            name=brand_name,
            defaults={"slug": f"{brand_name.lower()}-autos", "is_active": True},
        )
        model, _ = MarketModel.objects.get_or_create(
            brand=brand,
            category_slug=VEHICLE_SLUG,
            item_type="",
            name=model_name,
            defaults={"slug": f"{model_name.lower()}-autos", "is_active": True},
        )
        return brand, model

    def test_featured_order_priority(self) -> None:
        older = Listing.objects.create(
            title="Featured older",
            description="x" * 50,
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat_autos,
            status=Listing.Status.PUBLISHED,
            featured_until=timezone.now() + timedelta(days=7),
            boost_score=0,
        )
        self._vehicle_ext(older)
        newer = Listing.objects.create(
            title="Plain newer high quality",
            description="y" * 50,
            price_amount="2000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat_autos,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle_ext(newer)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/")
        qs = Listing.objects.published().filter(category=self.cat_autos)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ids = list(qs.values_list("id", flat=True)[:10])
        self.assertEqual(ids[0], older.id, "destacado debe ir primero aunque tenga menor quality_score")

    def test_quality_score_computation(self) -> None:
        listing = Listing(
            description="a" * 121,
            price_amount=Decimal("50.00"),
            currency="USD",
            zone=self.zone,
            title="T",
            slug="tmp-qual",
            seller_id=self.seller.id,
            category_id=self.cat_autos.id,
            status=Listing.Status.PUBLISHED,
        )
        self.assertEqual(compute_listing_quality_score(listing), 3.0)

        brand, model = self._market_model("Toy", "Corolla")
        v = VehicleListing(
            brand_fk=brand,
            model_fk=model,
            year=2019,
            doors=4,
            transmission=VehicleListing.Transmission.AUTOMATICO,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )
        listing.__dict__["vehicle"] = v
        self.assertEqual(compute_listing_quality_score(listing), 5.0)

        listing._prefetched_objects_cache = {"images": [object()]}
        self.assertEqual(compute_listing_quality_score(listing), 7.0)

    def test_non_featured_sorted_by_quality(self) -> None:
        past = timezone.now() - timedelta(days=1)
        high_q = Listing.objects.create(
            title="High Q",
            description="h" * 130,
            price_amount="3000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat_autos,
            status=Listing.Status.PUBLISHED,
            featured_until=past,
            boost_score=0,
        )
        self._vehicle_ext(high_q)
        low_q = Listing.objects.create(
            title="Low Q",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat_autos,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle_ext(low_q)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/")
        qs = Listing.objects.published().filter(category=self.cat_autos)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ids = list(qs.values_list("id", flat=True)[:10])
        self.assertLess(ids.index(high_q.id), ids.index(low_q.id))
