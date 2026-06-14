from django.core import mail
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.analytics.models import Event
from apps.categories.models import Category
from apps.listings.models import Listing, MarketZone

from .emails import send_user_otp_email
from .models import NewsletterSubscriber


@override_settings(
    PUBLIC_SITE_URL="https://anunciateya.test",
    PUBLIC_SITE_DOMAIN="anunciateya.test",
    SITE_NAME="anunciateya.test",
    SEO_BRAND_NAME="AnunciateYa",
    SEO_MARKET_CITY="Guayaquil",
    SOCIAL_SHARE_IMAGE_PATH="img/AnunciateYa_ShareImage_Home.png",
)
class SocialShareMetaTests(TestCase):
    share_image_url = (
        "https://anunciateya.test/static/img/AnunciateYa_ShareImage_Home.png"
    )

    def assert_social_share_meta(self, response, path):
        self.assertContains(
            response,
            f'<meta property="og:image" content="{self.share_image_url}">',
            html=True,
        )
        self.assertContains(
            response,
            f'<meta property="og:image:secure_url" content="{self.share_image_url}">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta property="og:image:type" content="image/png">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="twitter:card" content="summary_large_image">',
            html=True,
        )
        self.assertContains(
            response,
            f'<meta name="twitter:image" content="{self.share_image_url}">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta property="og:image:width" content="1200">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta property="og:image:height" content="630">',
            html=True,
        )
        self.assertContains(
            response,
            f'<link rel="canonical" href="https://anunciateya.test{path}">',
            html=True,
        )

    def test_public_base_pages_render_social_share_image(self):
        response = self.client.get(reverse("root_home"))

        self.assertEqual(response.status_code, 200)
        self.assert_social_share_meta(response, "/")
        self.assertContains(
            response,
            '<link rel="manifest" href="/manifest.webmanifest">',
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="theme-color" content="#3CBB6B">',
            html=True,
        )

    def test_auth_base_pages_render_social_share_image(self):
        response = self.client.get(reverse("users:login"))

        self.assertEqual(response.status_code, 200)
        self.assert_social_share_meta(response, "/ingresar/")

    def test_account_base_pages_render_social_share_image(self):
        user = get_user_model().objects.create_user(email="persona@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("users:account"))

        self.assertEqual(response.status_code, 200)
        self.assert_social_share_meta(response, "/mi-cuenta/")


class NewsletterSignupTests(TestCase):
    def test_htmx_signup_creates_subscriber_and_tracks_event(self):
        response = self.client.post(
            reverse("core:newsletter_signup"),
            {"email": " Persona@Example.COM "},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Te sumamos al newsletter")
        subscriber = NewsletterSubscriber.objects.get()
        self.assertEqual(subscriber.email, "persona@example.com")
        self.assertTrue(subscriber.is_active)
        event = Event.objects.get()
        self.assertEqual(event.event_type, "newsletter_signup")
        self.assertEqual(event.event_detail, "footer")
        self.assertEqual(event.path, "/")

    def test_duplicate_signup_is_friendly_and_does_not_duplicate(self):
        NewsletterSubscriber.objects.create(email="persona@example.com")

        response = self.client.post(
            reverse("core:newsletter_signup"),
            {"email": "persona@example.com"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya estaba suscrito")
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        self.assertEqual(Event.objects.count(), 0)

    def test_inactive_signup_reactivates_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(
            email="persona@example.com",
            is_active=False,
        )

        response = self.client.post(
            reverse("core:newsletter_signup"),
            {"email": "persona@example.com"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        self.assertEqual(Event.objects.count(), 1)

    def test_invalid_email_returns_inline_error(self):
        response = self.client.post(
            reverse("core:newsletter_signup"),
            {"email": "no-es-email"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Ingresá un email válido", status_code=400)
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PUBLIC_SITE_URL="https://anunciateya.test",
    PUBLIC_SITE_DOMAIN="anunciateya.test",
    SITE_NAME="anunciateya.test",
    SEO_BRAND_NAME="AnunciateYa",
    DEFAULT_FROM_EMAIL="hola@anunciateya.test",
    EMAIL_FROM_NAME="AnunciateYa",
    BRAND_LOGO_PATH="img/AnunciateYa_Logo.png",
)
class EmailTemplateTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_user_otp_email_uses_branded_html_template(self):
        send_user_otp_email("persona@example.com", "482731", 10)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Tu código de AnunciateYa vence en 10 min")
        self.assertEqual(message.from_email, "AnunciateYa <hola@anunciateya.test>")
        self.assertIn("482731", message.body)
        self.assertEqual(len(message.alternatives), 1)

        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn("Código de acceso", html_body)
        self.assertIn(
            "https://anunciateya.test/static/img/AnunciateYa_Logo.png",
            html_body,
        )
        self.assertIn("482731", html_body)


class PageNotFoundTests(TestCase):
    @override_settings(DEBUG=False)
    def test_generic_404_uses_branded_template(self):
        response = self.client.get("/ruta-inexistente/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página no encontrada", status_code=404)
        self.assertContains(response, "Ir al home", status_code=404)


@override_settings(
    SEO_BRAND_NAME="AnunciateYa",
    SEO_MARKET_CITY="Guayaquil",
    BRAND_THEME_COLOR="#3CBB6B",
    BRAND_PWA_ICON_PATH="img/AnunciateYa_PWA_Icon.png",
)
class ProgressiveWebAppTests(TestCase):
    def test_webmanifest_uses_branding_and_pwa_icon(self):
        response = self.client.get(reverse("webmanifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        payload = response.json()
        self.assertEqual(payload["name"], "AnunciateYa")
        self.assertEqual(payload["short_name"], "AnunciateYa")
        self.assertEqual(payload["start_url"], "/")
        self.assertEqual(payload["scope"], "/")
        self.assertEqual(payload["display"], "standalone")
        self.assertEqual(payload["theme_color"], "#3CBB6B")
        self.assertIn(
            {
                "src": "/static/img/AnunciateYa_PWA_Icon.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            payload["icons"],
        )
        self.assertTrue(any(icon["purpose"] == "maskable" for icon in payload["icons"]))
        self.assertEqual(payload["shortcuts"][0]["url"], "/publicar/")

    def test_service_worker_is_root_scoped_and_does_not_cache_html_pages(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/javascript; charset=utf-8",
        )
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        body = response.content.decode()
        self.assertIn('const OFFLINE_URL = "/offline/";', body)
        self.assertIn('request.mode === "navigate"', body)
        self.assertIn('fetch(request).catch(function ()', body)
        self.assertIn('requestUrl.pathname.startsWith(STATIC_PATH_PREFIX)', body)

    def test_offline_page_is_noindex(self):
        response = self.client.get(reverse("offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin conexión")
        self.assertContains(
            response,
            '<meta name="robots" content="noindex, nofollow">',
            html=True,
        )


class LegalPageTests(TestCase):
    def test_terms_page_renders(self):
        response = self.client.get(reverse("core:terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Términos de Servicio")
        self.assertContains(response, "AnunciateYa no actúa como vendedor")

    def test_privacy_page_renders(self):
        response = self.client.get(reverse("core:privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Política de Privacidad")
        self.assertContains(response, "AnunciateYa no vende información personal")


@override_settings(
    ALLOWED_HOSTS=["anunciateya.test", "testserver"],
    PUBLIC_SITE_URL="https://anunciateya.test",
    PUBLIC_SITE_DOMAIN="anunciateya.test",
    SITE_NAME="anunciateya.test",
)
class PublicDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = get_user_model().objects.create_user(email="seo@example.com")
        cls.category = Category.objects.create(
            name="Autos",
            slug="autos",
            order=1,
        )
        cls.zone = MarketZone.objects.get(slug="otro-guayaquil")
        cls.published_listing = Listing.objects.create(
            title="Toyota Publico",
            description="Auto publicado para sitemap.",
            price_amount="12000.00",
            currency="USD",
            zone=cls.zone,
            seller=cls.seller,
            category=cls.category,
            status=Listing.Status.PUBLISHED,
        )
        cls.draft_listing = Listing.objects.create(
            title="Toyota Borrador",
            description="Auto no publico.",
            price_amount="9000.00",
            currency="USD",
            zone=cls.zone,
            seller=cls.seller,
            category=cls.category,
            status=Listing.Status.DRAFT,
        )

    def test_robots_txt_points_to_sitemap_and_blocks_private_surfaces(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        body = response.content.decode()
        self.assertIn("User-agent: *", body)
        self.assertIn("Allow: /", body)
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /mi-cuenta/", body)
        self.assertIn("Disallow: /publicar/", body)
        self.assertIn("Disallow: /listings/", body)
        self.assertIn("Sitemap: https://anunciateya.test/sitemap.xml", body)

    def test_llms_txt_summarizes_public_site_for_ai_crawlers(self):
        response = self.client.get("/llms.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        body = response.content.decode()
        self.assertIn("# AnunciateYa", body)
        self.assertIn("marketplace de anuncios clasificados", body)
        self.assertIn("Sitemap XML: https://anunciateya.test/sitemap.xml", body)
        self.assertIn("Autos: https://anunciateya.test/autos/", body)
        self.assertIn("No uses rutas de cuenta", body)

    def test_sitemap_xml_exposes_only_public_indexable_urls(self):
        response = self.client.get("/sitemap.xml", HTTP_HOST="anunciateya.test")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("<loc>https://anunciateya.test/</loc>", body)
        self.assertIn("<loc>https://anunciateya.test/anuncios/</loc>", body)
        self.assertIn("<loc>https://anunciateya.test/publicar/</loc>", body)
        self.assertIn("<loc>https://anunciateya.test/autos/</loc>", body)
        self.assertIn(
            f"<loc>https://anunciateya.test{self.published_listing.get_absolute_url()}</loc>",
            body,
        )
        self.assertNotIn(self.draft_listing.get_absolute_url(), body)
