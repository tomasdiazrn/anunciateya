"""Promociones (featured / boost), ranking, expiración y endpoint promote."""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.categories.models import Category
from apps.listings.category_engine import apply_category_pipeline, build_category_page
from apps.listings.category_extensions import VEHICLE_SLUG
from apps.listings.models import Listing, ListingPromotion, VehicleListing
from apps.listings.services_promotions import create_listing_promotion

User = get_user_model()


class PromotionRankingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="promo_seller@example.com",
            password="x",
        )
        cls.cat, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )

    def _vehicle(self, listing: Listing) -> None:
        VehicleListing.objects.create(
            listing=listing,
            brand="B",
            model="M",
            year=2020,
            doors=4,
            mileage=1,
            transmission=VehicleListing.Transmission.MANUAL,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )

    def test_featured_promotion_appears_in_top_strip(self) -> None:
        plain = Listing.objects.create(
            title="Plain",
            description="d",
            price_amount="5000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=99,
        )
        self._vehicle(plain)
        paid = Listing.objects.create(
            title="PaidFeat",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle(paid)
        create_listing_promotion(
            paid,
            self.seller,
            "featured",
            7,
        )

        rf = RequestFactory()
        req = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        page = build_category_page(req, category_slug=VEHICLE_SLUG)
        self.assertTrue(page.featured_cards)
        self.assertEqual(page.featured_cards[0].listing_id, paid.pk)

    def test_boost_improves_order_vs_no_boost(self) -> None:
        slow = Listing.objects.create(
            title="Slow",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=10,
        )
        self._vehicle(slow)
        fast = Listing.objects.create(
            title="Fast",
            description="d",
            price_amount="2000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=10,
        )
        self._vehicle(fast)
        create_listing_promotion(
            fast,
            self.seller,
            "boost",
            7,
        )

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ids = list(qs.values_list("id", flat=True))
        self.assertEqual(ids[0], fast.pk)

    def test_expired_promotion_ignored(self) -> None:
        row = Listing.objects.create(
            title="Exp",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle(row)
        ListingPromotion.objects.create(
            listing=row,
            user=self.seller,
            type=ListingPromotion.PromotionType.BOOST,
            starts_at=timezone.now() - timedelta(days=14),
            ends_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        row_db = qs.get(pk=row.pk)
        self.assertEqual(int(getattr(row_db, "has_active_boost", -1)), 0)

    def test_multiple_promotions_same_listing(self) -> None:
        row = Listing.objects.create(
            title="Multi",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle(row)
        create_listing_promotion(
            row,
            self.seller,
            "featured",
            3,
        )
        create_listing_promotion(
            row,
            self.seller,
            "boost",
            3,
        )

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ann = qs.get(pk=row.pk)
        self.assertEqual(int(ann.has_active_featured), 1)
        self.assertEqual(int(ann.has_active_boost), 1)

    def test_legacy_featured_until_coexists_without_promo(self) -> None:
        row = Listing.objects.create(
            title="Legacy",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=timezone.now() + timedelta(days=2),
            boost_score=0,
        )
        self._vehicle(row)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ann = qs.get(pk=row.pk)
        self.assertEqual(int(ann.has_active_featured), 0)
        self.assertEqual(int(ann.is_featured), 1)


class ListingPromoteEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="promote_api@example.com",
            password="secret123",
        )
        cls.cat, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        cls.listing = Listing.objects.create(
            title="Api listing",
            description="d",
            price_amount="1000",
            currency="USD",
            location="Gye",
            seller=cls.seller,
            category=cls.cat,
            status=Listing.Status.PUBLISHED,
        )

    def test_promote_post_creates_promotion(self) -> None:
        c = Client()
        c.force_login(self.seller)
        url = reverse("listings:promote", kwargs={"pk": self.listing.pk})
        resp = c.post(
            url,
            data=json.dumps({"type": "featured", "days": 7}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content.decode())
        data = json.loads(resp.content.decode())
        self.assertEqual(data["listing_id"], self.listing.pk)
        self.assertTrue(
            ListingPromotion.objects.filter(
                listing=self.listing,
                type="featured",
            ).exists(),
        )

    def test_promote_forbidden_other_user(self) -> None:
        other = User.objects.create_user(
            email="other@example.com",
            password="secret123",
        )
        c = Client()
        c.force_login(other)
        url = reverse("listings:promote", kwargs={"pk": self.listing.pk})
        resp = c.post(
            url,
            data=json.dumps({"type": "boost", "days": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
