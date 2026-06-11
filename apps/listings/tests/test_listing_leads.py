from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.categories.models import Category
from apps.listings.models import Listing, ListingLead
from apps.users.models import UserVerification

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ListingLeadCaptureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Hogar", slug="hogar")

    def setUp(self):
        mail.outbox = []
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="ignored",
            first_name="Seller",
            last_name="Example",
            is_active=True,
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="ignored",
            first_name="Buyer",
            last_name="Example",
            is_active=True,
        )
        self.listing = Listing.objects.create(
            title="Mesa de madera",
            slug="mesa-de-madera",
            description="Mesa en buen estado",
            price_amount="120.00",
            currency="USD",
            location="Guayaquil",
            seller=self.seller,
            category=self.category,
            status=Listing.Status.PUBLISHED,
        )

    def _post_contact(self, **overrides):
        payload = {
            "buyer_name": "Buyer Example",
            "buyer_email": "buyer@example.com",
            "message": "Hola, sigue disponible esta mesa?",
            "accept_terms": "on",
        }
        payload.update(overrides)
        return self.client.post(
            reverse("listings:contact", kwargs={"slug": self.listing.slug}),
            payload,
        )

    def test_contact_form_persists_lead_and_sends_email(self):
        response = self._post_contact()

        self.assertRedirects(
            response,
            self.listing.get_absolute_url(),
            fetch_redirect_response=False,
        )
        lead = ListingLead.objects.get()
        self.assertEqual(lead.listing, self.listing)
        self.assertEqual(lead.seller, self.seller)
        self.assertEqual(lead.source, ListingLead.Source.FORM)
        self.assertEqual(lead.buyer_name, "Buyer Example")
        self.assertEqual(lead.buyer_email, "buyer@example.com")
        self.assertEqual(lead.email_status, ListingLead.EmailStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Mesa de madera", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["seller@example.com"])

    def test_contact_form_keeps_lead_when_email_fails(self):
        with patch("apps.listings.services.send_mail", side_effect=RuntimeError("SMTP down")):
            response = self._post_contact()

        self.assertRedirects(
            response,
            self.listing.get_absolute_url(),
            fetch_redirect_response=False,
        )
        lead = ListingLead.objects.get()
        self.assertEqual(lead.email_status, ListingLead.EmailStatus.FAILED)
        self.assertIn("SMTP down", lead.email_error)
        self.assertEqual(lead.message, "Hola, sigue disponible esta mesa?")

    def test_whatsapp_redirect_persists_contact_intent(self):
        UserVerification.objects.create(
            user=self.seller,
            phone_country_code="+593",
            phone_number="987654321",
            whatsapp_contact_enabled=True,
        )
        self.client.force_login(self.buyer)

        response = self.client.get(
            reverse("listings:whatsapp", kwargs={"slug": self.listing.slug})
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://wa.me/593987654321"))
        lead = ListingLead.objects.get()
        self.assertEqual(lead.source, ListingLead.Source.WHATSAPP)
        self.assertEqual(lead.buyer_user, self.buyer)
        self.assertEqual(lead.buyer_email, "buyer@example.com")
        self.assertEqual(lead.email_status, ListingLead.EmailStatus.NOT_APPLICABLE)
