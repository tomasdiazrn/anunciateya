from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.categories.models import Category
from apps.listings.listing_card_dto import build_card_context
from apps.listings.models import Listing, MarketZone

User = get_user_model()


class AdminMarketplaceAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="admin-marketplace@example.com",
            password="ignored",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        cls.category = Category.objects.create(name="Servicios", slug="servicios")
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")
        cls.listing = Listing.objects.create(
            title="Anuncio admin",
            description="No debe editarse desde el marketplace.",
            price_amount="100.00",
            currency="USD",
            zone=cls.zone,
            seller=cls.admin,
            category=cls.category,
            status=Listing.Status.PUBLISHED,
            published_by_platform=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def assertRedirectsToAdmin(self, response):
        self.assertRedirects(response, reverse("adminapp:dashboard"))

    def test_staff_publish_redirects_to_admin_panel(self):
        self.assertRedirectsToAdmin(self.client.get(reverse("publish")))

    def test_staff_publish_category_redirects_to_admin_panel(self):
        self.assertRedirectsToAdmin(
            self.client.get(
                reverse("publish_in_category", kwargs={"category_slug": self.category.slug})
            )
        )

    def test_staff_can_open_admin_publish_flow(self):
        response = self.client.get(reverse("adminapp:listing_publish"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publicar anuncio")
        self.assertContains(
            response,
            reverse(
                "adminapp:listing_publish_in_category",
                kwargs={"category_slug": self.category.slug},
            ),
        )

    def test_staff_can_create_platform_listing_from_admin_panel(self):
        response = self.client.post(
            reverse(
                "adminapp:listing_publish_in_category",
                kwargs={"category_slug": self.category.slug},
            ),
            {
                "title": "Servicio publicado por admin",
                "description": "Anuncio creado desde el panel administrativo.",
                "price_amount": "49",
                "zone": self.zone.pk,
                "location_reference": "",
                "publish_state": Listing.Status.PUBLISHED,
            },
        )

        listing = Listing.objects.get(title="Servicio publicado por admin")
        self.assertRedirects(
            response,
            reverse("adminapp:listing_detail", kwargs={"pk": listing.pk}),
        )
        self.assertEqual(listing.seller, self.admin)
        self.assertTrue(listing.published_by_platform)
        self.assertTrue(listing.is_platform_listing)
        self.assertEqual(listing.status, Listing.Status.PUBLISHED)

    def test_platform_listing_card_shows_publisher_label(self):
        card = build_card_context(
            self.listing,
            self.listing.category.slug,
            trust_map={},
        )

        self.assertEqual(card.publisher_label, "Publicado por AnunciateYa")

    def test_staff_my_listings_redirects_to_admin_panel(self):
        self.assertRedirectsToAdmin(self.client.get(reverse("listings:mine")))

    def test_staff_listing_edit_redirects_to_admin_panel(self):
        self.assertRedirectsToAdmin(
            self.client.get(reverse("users:account_listing_edit", kwargs={"slug": self.listing.slug}))
        )

    def test_staff_listing_delete_redirects_to_admin_panel(self):
        self.assertRedirectsToAdmin(
            self.client.get(reverse("listings:delete", kwargs={"slug": self.listing.slug}))
        )
