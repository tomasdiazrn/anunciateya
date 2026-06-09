from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.analytics.models import Event

from .emails import send_user_otp_email
from .models import NewsletterSubscriber


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
    BRAND_LOGO_PATH="img/AnunciateYa_Logo.png",
)
class EmailTemplateTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_user_otp_email_uses_branded_html_template(self):
        send_user_otp_email("persona@example.com", "482731", 10)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("482731", message.body)
        self.assertEqual(len(message.alternatives), 1)

        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn("Código de ingreso", html_body)
        self.assertIn("https://anunciateya.test/static/img/AnunciateYa_Logo.png", html_body)
        self.assertIn("482731", html_body)


class PageNotFoundTests(TestCase):
    @override_settings(DEBUG=False)
    def test_generic_404_uses_branded_template(self):
        response = self.client.get("/ruta-inexistente/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página no encontrada", status_code=404)
        self.assertContains(response, "Ir al home", status_code=404)


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
