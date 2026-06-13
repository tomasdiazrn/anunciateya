"""Parámetro ?sort=, orden, pin featured_top y canonical SEO."""

from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from apps.categories.models import Category
from apps.listings.category_engine import apply_category_pipeline, build_category_page
from apps.listings.category_extensions import VEHICLE_SLUG
from apps.listings.listing_sort import (
    ALLOWED_SORTS,
    apply_listing_order,
    parse_sort_param,
    split_featured_block,
)
from apps.listings.models import Listing, MarketBrand, MarketModel, MarketZone, VehicleListing

User = get_user_model()


class ListingSortParamTests(TestCase):
    def test_parse_sort_param_whitelist(self) -> None:
        rf = RequestFactory()
        self.assertEqual(parse_sort_param(rf.get("/x/", {"sort": "newest"})), "newest")
        self.assertEqual(parse_sort_param(rf.get("/x/", {"sort": "bogus"})), "relevance")
        self.assertEqual(parse_sort_param(rf.get("/x/")), "relevance")

    def test_allowed_sorts_contains_expected(self) -> None:
        self.assertEqual(
            ALLOWED_SORTS,
            frozenset({"relevance", "newest", "price_asc", "price_desc"}),
        )


class ListingSortOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="sort_seller@example.com",
            password="x",
        )
        cls.cat, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

    def _vehicle(self, listing: Listing) -> None:
        brand, model = self._market_model("B", "M")
        VehicleListing.objects.create(
            listing=listing,
            brand_fk=brand,
            model_fk=model,
            year=2020,
            doors=4,
            mileage=1,
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

    def test_sort_relevance_orders_by_boost_not_featured_pin(self) -> None:
        plain = Listing.objects.create(
            title="Plain",
            description="d",
            price_amount="5000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=10,
        )
        self._vehicle(plain)
        feat = Listing.objects.create(
            title="Feat",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=timezone.now() + timedelta(days=1),
            boost_score=0,
        )
        self._vehicle(feat)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ids = list(qs.values_list("id", flat=True))
        self.assertEqual(ids[0], plain.id)

    def test_sort_newest_ignores_featured_in_sql_order(self) -> None:
        old_feat = Listing.objects.create(
            title="Old feat",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=timezone.now() + timedelta(days=1),
            boost_score=0,
        )
        self._vehicle(old_feat)
        new_plain = Listing.objects.create(
            title="New plain",
            description="d",
            price_amount="2000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=0,
        )
        self._vehicle(new_plain)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "newest"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        ids = list(qs.values_list("id", flat=True))
        self.assertEqual(ids[0], new_plain.id)

    def test_sort_price_asc_desc(self) -> None:
        hi = Listing.objects.create(
            title="Hi",
            description="d",
            price_amount="9000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
        )
        self._vehicle(hi)
        lo = Listing.objects.create(
            title="Lo",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
        )
        self._vehicle(lo)

        rf = RequestFactory()
        base = Listing.objects.published().filter(category=self.cat)
        qs_asc, _, _ = apply_category_pipeline(
            rf.get(f"/{VEHICLE_SLUG}/", {"sort": "price_asc"}),
            base,
            VEHICLE_SLUG,
        )
        self.assertEqual(list(qs_asc.values_list("id", flat=True)[:2]), [lo.id, hi.id])

        qs_desc, _, _ = apply_category_pipeline(
            rf.get(f"/{VEHICLE_SLUG}/", {"sort": "price_desc"}),
            base,
            VEHICLE_SLUG,
        )
        self.assertEqual(list(qs_desc.values_list("id", flat=True)[:2]), [hi.id, lo.id])

    def test_split_featured_block_caps_featured_same_qs_for_pagination(self) -> None:
        listings: list[Listing] = []
        for i in range(4):
            listings.append(
                Listing.objects.create(
                    title=f"F{i}",
                    description="d",
                    price_amount=str(1000 + i),
                    currency="USD",
                    zone=self.zone,
                    seller=self.seller,
                    category=self.cat,
                    status=Listing.Status.PUBLISHED,
                    featured_until=timezone.now() + timedelta(days=1),
                    boost_score=0,
                ),
            )
            self._vehicle(listings[-1])
        plain = Listing.objects.create(
            title="P",
            description="d",
            price_amount="9999",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
        )
        self._vehicle(plain)

        rf = RequestFactory()
        request = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        qs = Listing.objects.published().filter(category=self.cat)
        qs, _, _ = apply_category_pipeline(request, qs, VEHICLE_SLUG)
        featured_qs, normal_qs = split_featured_block(qs, limit=3)
        feat_ids = list(featured_qs.values_list("id", flat=True))
        self.assertEqual(len(feat_ids), 3)
        normal_id_set = set(normal_qs.values_list("id", flat=True))
        self.assertIn(plain.id, normal_id_set)
        for fid in feat_ids:
            self.assertIn(fid, normal_id_set)


class CanonicalSortSeoTests(TestCase):
    def test_canonical_hub_ignores_sort_querystring(self) -> None:
        Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        c = Client()
        resp = c.get(f"/{VEHICLE_SLUG}/?sort=price_desc")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        self.assertIsNotNone(m, msg=html[:500])
        href = m.group(1)
        self.assertNotIn("sort=", href)
        self.assertTrue(href.endswith(f"/{VEHICLE_SLUG}/") or href.rstrip("/").endswith(VEHICLE_SLUG))


class FeaturedTopCardContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="ftop_seller@example.com",
            password="x",
        )
        cls.cat, _ = Category.objects.get_or_create(
            slug=VEHICLE_SLUG,
            defaults={"name": "Autos", "order": 0},
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")

    def _vehicle(self, listing: Listing) -> None:
        brand, model = self._market_model("B", "M")
        VehicleListing.objects.create(
            listing=listing,
            brand_fk=brand,
            model_fk=model,
            year=2020,
            doors=4,
            mileage=1,
            transmission=VehicleListing.Transmission.MANUAL,
            fuel_type=VehicleListing.FuelType.GASOLINA,
        )

    def _market_model(self, brand_name: str, model_name: str):
        brand, _ = MarketBrand.objects.get_or_create(
            name=f"{brand_name} featured",
            defaults={"slug": f"{brand_name.lower()}-featured-autos", "is_active": True},
        )
        model, _ = MarketModel.objects.get_or_create(
            brand=brand,
            category_slug=VEHICLE_SLUG,
            item_type="",
            name=model_name,
            defaults={"slug": f"{model_name.lower()}-featured-autos", "is_active": True},
        )
        return brand, model

    def test_featured_top_cards_marked_first_page(self) -> None:
        for i in range(3):
            l = Listing.objects.create(
                title=f"Top{i}",
                description="d",
                price_amount=str(2000 + i),
                currency="USD",
                zone=self.zone,
                seller=self.seller,
                category=self.cat,
                status=Listing.Status.PUBLISHED,
                featured_until=timezone.now() + timedelta(days=2),
            )
            self._vehicle(l)
        rf = RequestFactory()
        req = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        page = build_category_page(req, category_slug=VEHICLE_SLUG)
        featured = page.featured_cards
        self.assertGreaterEqual(len(featured), 3)
        for card in featured:
            self.assertTrue(card.is_featured_top, msg=f"card {card.title!r}")

    def test_featured_not_duplicated_between_blocks(self) -> None:
        feat = Listing.objects.create(
            title="StripFeat",
            description="d",
            price_amount="1000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=timezone.now() + timedelta(days=1),
            boost_score=0,
        )
        self._vehicle(feat)
        plain = Listing.objects.create(
            title="GridPlain",
            description="d",
            price_amount="2000",
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            featured_until=None,
            boost_score=10,
        )
        self._vehicle(plain)
        rf = RequestFactory()
        req = rf.get(f"/{VEHICLE_SLUG}/", {"sort": "relevance"})
        page = build_category_page(req, category_slug=VEHICLE_SLUG)
        featured_ids = {c.listing_id for c in page.featured_cards}
        normal_ids = {c.listing_id for c in page.normal_cards}
        self.assertIn(feat.pk, featured_ids)
        self.assertTrue(featured_ids.isdisjoint(normal_ids))
