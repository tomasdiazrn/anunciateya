from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.core import mail
from django.template.defaultfilters import date as date_filter
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.categories.models import Category
from apps.core.models import NewsletterSubscriber
from apps.listings.models import Listing
from apps.users.models import User, UserLoginOTP, UserVerification

from .hosting import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXPIRING,
    STATUS_NOT_CONFIGURED,
    get_hosting_membership,
)


class HostingAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-hosting@example.com",
            password="ignored",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            email="regular-hosting@example.com",
            password="ignored",
            is_active=True,
        )

    def test_membership_statuses_from_configured_dates(self):
        today = timezone.localdate()

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today + timezone.timedelta(days=45)),
        ):
            self.assertEqual(get_hosting_membership(today).status, STATUS_ACTIVE)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today + timezone.timedelta(days=7)),
        ):
            self.assertEqual(get_hosting_membership(today).status, STATUS_EXPIRING)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today - timezone.timedelta(days=30)),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today - timezone.timedelta(days=1)),
        ):
            membership = get_hosting_membership(today)
            self.assertEqual(membership.status, STATUS_EXPIRED)
            self.assertEqual(membership.absolute_days_remaining, 1)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE="",
            HOSTING_MEMBERSHIP_EXPIRES_DATE="",
        ):
            self.assertEqual(get_hosting_membership(today).status, STATUS_NOT_CONFIGURED)

    @override_settings(
        HOSTING_MEMBERSHIP_START_DATE="2026-01-01",
        HOSTING_MEMBERSHIP_EXPIRES_DATE="2027-01-01",
        HOSTING_RENEWAL_URL="https://altovalleit.com/hosting/",
        SITE_NAME="anunciateya.com",
    )
    def test_staff_can_view_hosting_page(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:hosting"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminapp/hosting/detail.html")
        self.assertEqual(response.context["admin_section"], "hosting")
        self.assertContains(response, "Hosting activo")
        self.assertContains(response, "Renovar con AltoValleIT")
        self.assertContains(response, "utm_source=anunciateya_admin")
        self.assertContains(response, "site_name=anunciateya.com")

    @override_settings(
        HOSTING_MEMBERSHIP_START_DATE="2026-01-01",
        HOSTING_MEMBERSHIP_EXPIRES_DATE="2027-01-01",
    )
    def test_hosting_page_supports_htmx_fragment(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:hosting"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminapp/fragments/hosting_main.html")
        self.assertContains(response, "Estado de membresía")
        self.assertNotContains(response, "<html")

    def test_expiring_membership_shows_admin_alert(self):
        today = timezone.localdate()
        self.client.force_login(self.admin)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today - timezone.timedelta(days=30)),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today + timezone.timedelta(days=7)),
        ):
            response = self.client.get(reverse("adminapp:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu hosting vence en 7 días")
        self.assertContains(response, "data-close-hosting-popup")

    def test_expired_membership_shows_blocking_popup(self):
        today = timezone.localdate()
        self.client.force_login(self.admin)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today - timezone.timedelta(days=30)),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today - timezone.timedelta(days=1)),
        ):
            response = self.client.get(reverse("adminapp:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hosting vencido")
        self.assertContains(response, "admin-hosting-popup--blocking")
        self.assertNotContains(response, "data-close-hosting-popup")

    def test_hosting_alerts_do_not_render_for_non_staff_public_pages(self):
        today = timezone.localdate()
        self.client.force_login(self.user)

        with override_settings(
            HOSTING_MEMBERSHIP_START_DATE=str(today - timezone.timedelta(days=30)),
            HOSTING_MEMBERSHIP_EXPIRES_DATE=str(today - timezone.timedelta(days=7)),
        ):
            response = self.client.get(reverse("root_home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "admin-hosting-alert")
        self.assertNotContains(response, "admin-hosting-popup")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminAccessTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="old-password",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        self.user = User.objects.create_user(
            email="user@example.com",
            password="ignored",
            is_active=True,
        )

    def _request_code(self, email="admin@example.com", code="123456"):
        with patch("apps.users.otp_auth.generate_user_otp_code", return_value=code):
            return self.client.post(
                reverse("users:login"),
                {"action": "request_code", "email": email},
            )

    def test_unauthenticated_admin_redirects_to_unified_login(self):
        response = self.client.get(reverse("adminapp:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next=/admin/",
        )

    def test_legacy_admin_login_url_redirects_to_unified_login(self):
        response = self.client.get(reverse("adminapp:login"))

        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={reverse('adminapp:dashboard')}",
        )

    def test_staff_login_via_unified_flow_reaches_dashboard(self):
        self._request_code(code="123456")
        response = self.client.post(
            reverse("users:login"),
            {"action": "verify_code", "code": "123456"},
        )

        self.assertRedirects(response, reverse("adminapp:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)

    def test_staff_login_with_next_returns_to_admin(self):
        self.client.get(f"{reverse('users:login')}?next=/admin/anuncios/")
        self._request_code(code="123456")
        response = self.client.post(
            reverse("users:login"),
            {"action": "verify_code", "code": "123456"},
        )

        self.assertRedirects(response, "/admin/anuncios/")

    def test_non_staff_cannot_access_admin_panel(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("adminapp:dashboard"))

        self.assertRedirects(response, reverse("users:account"))

    def test_non_staff_admin_htmx_redirects_to_account(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("adminapp:dashboard"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], reverse("users:account"))

    def test_staff_receives_otp_via_unified_login(self):
        response = self._request_code(code="482731")

        self.assertEqual(response.status_code, 200)
        otp = UserLoginOTP.objects.get()
        self.assertEqual(otp.email, "admin@example.com")
        self.assertTrue(check_password("482731", otp.code_hash))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("482731", mail.outbox[0].body)

    def test_logout_flushes_session(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("adminapp:logout"))

        self.assertRedirects(response, reverse("root_home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_can_list_newsletter_subscribers(self):
        NewsletterSubscriber.objects.create(email="suscriptor@example.com")
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:newsletter_subscribers"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsletter")
        self.assertContains(response, "Se suscribió")
        self.assertContains(response, "suscriptor@example.com")
        self.assertContains(response, 'role="switch"')
        self.assertContains(response, 'aria-label="Desactivar suscriptor suscriptor@example.com"')
        self.assertContains(response, 'aria-checked="true"')

    def test_newsletter_subscriber_search_filters_by_email(self):
        NewsletterSubscriber.objects.create(email="uno@example.com")
        NewsletterSubscriber.objects.create(email="dos@example.com")
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:newsletter_subscribers"),
            {"q": "uno"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "uno@example.com")
        self.assertNotContains(response, "dos@example.com")

    def test_newsletter_subscriber_status_filter_shows_only_active(self):
        NewsletterSubscriber.objects.create(email="enabled@example.com")
        NewsletterSubscriber.objects.create(
            email="disabled@example.com",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:newsletter_subscribers"),
            {"visibility": "active"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_visibility"], "active")
        self.assertTrue(response.context["has_filters"])
        self.assertContains(response, "enabled@example.com")
        self.assertNotContains(response, "disabled@example.com")

    def test_newsletter_subscriber_status_filter_shows_only_inactive(self):
        NewsletterSubscriber.objects.create(email="enabled@example.com")
        NewsletterSubscriber.objects.create(
            email="disabled@example.com",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:newsletter_subscribers"),
            {"visibility": "inactive"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_visibility"], "inactive")
        self.assertTrue(response.context["has_filters"])
        self.assertContains(response, "disabled@example.com")
        self.assertNotContains(response, "enabled@example.com")

    def test_staff_can_deactivate_newsletter_subscriber_from_table(self):
        subscriber = NewsletterSubscriber.objects.create(email="suscriptor@example.com")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "adminapp:newsletter_subscriber_toggle_active",
                kwargs={"pk": subscriber.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)
        self.assertContains(response, 'aria-label="Activar suscriptor suscriptor@example.com"')
        self.assertContains(response, 'aria-checked="false"')

    def test_staff_can_reactivate_newsletter_subscriber_from_table(self):
        subscriber = NewsletterSubscriber.objects.create(
            email="suscriptor@example.com",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "adminapp:newsletter_subscriber_toggle_active",
                kwargs={"pk": subscriber.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertContains(response, 'aria-label="Desactivar suscriptor suscriptor@example.com"')
        self.assertContains(response, 'aria-checked="true"')

    def test_listings_table_does_not_include_id_column(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:listings"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ID", response.context["listing_table_headers"])

    def test_listings_table_uses_status_toggle_for_visibility(self):
        category = Category.objects.create(name="Admin listings", slug="admin-listings")
        listing = Listing.objects.create(
            title="Visible admin listing",
            description="Listing shown in the custom admin table.",
            price_amount="10.00",
            location="Montevideo Centro",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
            is_flagged=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:listings"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["listing_table_headers"][0], "Publicación")
        self.assertIn("Categoría", response.context["listing_table_headers"])
        self.assertIn("Precio", response.context["listing_table_headers"])
        self.assertIn("Reportado", response.context["listing_table_headers"])
        self.assertNotIn("Ubicación", response.context["listing_table_headers"])
        self.assertIn("Estado", response.context["listing_table_headers"])
        self.assertNotIn("Visible", response.context["listing_table_headers"])
        self.assertContains(
            response,
            date_filter(timezone.localtime(listing.created_at), "Y-m-d H:i"),
        )
        self.assertContains(response, "Admin listings")
        self.assertContains(response, "$")
        self.assertContains(response, "$ 10")
        self.assertNotContains(response, "10,00")
        self.assertNotContains(response, "USD")
        self.assertContains(response, "Reportado")
        self.assertNotContains(response, "Montevideo Centro")
        self.assertContains(response, 'role="switch"')
        self.assertContains(
            response,
            'aria-label="Guardar como borrador anuncio Visible admin listing"',
        )
        self.assertContains(
            response,
            "¿Seguro quieres guardar como borrador el anuncio Visible admin listing?",
        )
        listing_detail_url = reverse(
            "adminapp:listing_detail",
            kwargs={"pk": listing.pk},
        )
        self.assertContains(response, f'href="{listing.get_absolute_url()}"')
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, f'href="{listing_detail_url}"')
        self.assertContains(response, f'hx-get="{listing_detail_url}"')
        self.assertContains(response, 'aria-label="Ver anuncio Visible admin listing"')
        self.assertContains(
            response,
            'aria-label="Archivar anuncio Visible admin listing"',
        )
        self.assertContains(
            response,
            'aria-label="Eliminar anuncio Visible admin listing"',
        )
        self.assertContains(
            response,
            "¿Estás seguro de eliminar el anuncio Visible admin listing?",
        )
        self.assertNotContains(response, "Cambiar estado")
        self.assertNotContains(response, ">Ocultar<")
        self.assertNotContains(response, ">Mostrar<")
        self.assertNotContains(response, ">Ver<")

    def test_listings_table_filters_by_category(self):
        vehicles = Category.objects.create(name="Vehículos", slug="vehiculos")
        property_category = Category.objects.create(
            name="Inmuebles",
            slug="inmuebles",
        )
        Listing.objects.create(
            title="Auto filtrado",
            description="Listing matching the selected category.",
            price_amount="10.00",
            seller=self.user,
            category=vehicles,
            status=Listing.Status.PUBLISHED,
        )
        Listing.objects.create(
            title="Casa filtrada",
            description="Listing outside the selected category.",
            price_amount="20.00",
            seller=self.user,
            category=property_category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:listings"),
            {"category": vehicles.slug},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Auto filtrado")
        self.assertNotContains(response, "Casa filtrada")
        self.assertContains(response, 'name="category"')
        self.assertContains(response, f'value="{vehicles.slug}"')
        self.assertContains(response, "selected")

    def test_listings_table_filters_by_active_visibility(self):
        category = Category.objects.create(name="Estados", slug="estados")
        Listing.objects.create(
            title="Anuncio activo",
            description="Published listing shown as active.",
            price_amount="10.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        Listing.objects.create(
            title="Anuncio borrador",
            description="Draft listing hidden from active filter.",
            price_amount="20.00",
            seller=self.user,
            category=category,
            status=Listing.Status.DRAFT,
        )
        Listing.objects.create(
            title="Anuncio archivado",
            description="Archived listing hidden from active filter.",
            price_amount="30.00",
            seller=self.user,
            category=category,
            status=Listing.Status.ARCHIVED,
        )
        self.client.force_login(self.admin)

        active_response = self.client.get(
            reverse("adminapp:listings"),
            {"visibility": "active"},
        )

        self.assertEqual(active_response.status_code, 200)
        self.assertContains(active_response, "Anuncio activo")
        self.assertNotContains(active_response, "Anuncio borrador")
        self.assertNotContains(active_response, "Anuncio archivado")
        self.assertContains(active_response, 'value="active"')

        inactive_response = self.client.get(
            reverse("adminapp:listings"),
            {"visibility": "inactive"},
        )

        self.assertEqual(inactive_response.status_code, 200)
        self.assertNotContains(inactive_response, "Anuncio activo")
        self.assertContains(inactive_response, "Anuncio borrador")
        self.assertContains(inactive_response, "Anuncio archivado")

    def test_staff_can_view_listing_detail_in_admin(self):
        category = Category.objects.create(name="Detail category", slug="detail-category")
        listing = Listing.objects.create(
            title="Admin detail listing",
            description="Listing rendered in the dedicated admin detail view.",
            price_amount="42.00",
            location="Quito Norte",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
            is_flagged=True,
        )
        self.client.force_login(self.admin)
        detail_url = reverse("adminapp:listing_detail", kwargs={"pk": listing.pk})

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminapp/listings/detail.html")
        self.assertEqual(response.context["admin_section"], "listings")
        self.assertContains(response, "Admin detail listing")
        self.assertContains(response, "Detail category")
        self.assertContains(response, "Quito Norte")
        self.assertContains(response, "user@example.com")
        self.assertContains(response, "Ver anuncio público")
        self.assertContains(response, f'href="{listing.get_absolute_url()}"')

        htmx_response = self.client.get(detail_url, HTTP_HX_REQUEST="true")

        self.assertEqual(htmx_response.status_code, 200)
        self.assertTemplateUsed(
            htmx_response,
            "adminapp/fragments/listing_detail_main.html",
        )
        self.assertContains(htmx_response, "← Anuncios")

    def test_staff_can_move_listing_to_draft_from_status_column(self):
        category = Category.objects.create(name="Toggle listing", slug="toggle-listing")
        listing = Listing.objects.create(
            title="Toggle me",
            description="Listing visibility toggled from the status column.",
            price_amount="15.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:listing_set_status", kwargs={"pk": listing.pk}),
            {"status": Listing.Status.DRAFT},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.DRAFT)
        self.assertContains(response, 'aria-label="Publicar anuncio Toggle me"')
        self.assertContains(response, 'aria-checked="false"')

    def test_staff_can_archive_listing_from_actions_column(self):
        category = Category.objects.create(name="Archive listing", slug="archive-listing")
        listing = Listing.objects.create(
            title="Archive me",
            description="Listing archived from the actions column.",
            price_amount="15.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:listing_archive", kwargs={"pk": listing.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.ARCHIVED)
        self.assertContains(
            response,
            'aria-label="Anuncio archivado Archive me. Desarchivalo para poder publicarlo."',
        )
        self.assertContains(response, "Archivado: desarchivalo para poder publicarlo.")
        self.assertContains(response, 'aria-label="Desarchivar anuncio Archive me"')
        self.assertNotContains(response, 'aria-label="Archivar anuncio Archive me"')

    def test_staff_can_unarchive_listing_from_actions_column(self):
        category = Category.objects.create(
            name="Unarchive listing",
            slug="unarchive-listing",
        )
        listing = Listing.objects.create(
            title="Unarchive me",
            description="Listing restored from the actions column.",
            price_amount="15.00",
            seller=self.user,
            category=category,
            status=Listing.Status.ARCHIVED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:listing_unarchive", kwargs={"pk": listing.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.DRAFT)
        self.assertContains(response, 'aria-label="Publicar anuncio Unarchive me"')
        self.assertContains(response, 'aria-label="Archivar anuncio Unarchive me"')
        self.assertNotContains(
            response,
            'aria-label="Desarchivar anuncio Unarchive me"',
        )

    def test_set_status_does_not_archive_listing(self):
        category = Category.objects.create(name="No archive", slug="no-archive")
        listing = Listing.objects.create(
            title="No archive from status",
            description="Archived status must be handled by the action endpoint.",
            price_amount="15.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:listing_set_status", kwargs={"pk": listing.pk}),
            {"status": Listing.Status.ARCHIVED},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.PUBLISHED)
        self.assertContains(
            response,
            'aria-label="Guardar como borrador anuncio No archive from status"',
        )

    def test_staff_can_delete_listing_from_listings_table(self):
        category = Category.objects.create(name="Delete listing", slug="delete-listing")
        listing = Listing.objects.create(
            title="Delete me listing",
            description="Listing removed from the admin table.",
            price_amount="15.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:listing_delete", kwargs={"pk": listing.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())

    def test_users_table_shows_phone_verification_without_staff_actions(self):
        UserVerification.objects.create(
            user=self.user,
            phone_country_code="+593",
            phone_number="987654321",
            phone_verified=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ID", response.context["user_table_headers"])
        self.assertNotIn("Verificado", response.context["user_table_headers"])
        self.assertContains(response, "Teléfono")
        self.assertContains(response, "+593 987654321")
        self.assertContains(response, "Teléfono verificado")
        self.assertContains(response, "Usuario admin")
        self.assertEqual(response.content.count(b"admin-role-icon--admin"), 1)
        self.assertNotContains(response, "Teléfono sin verificar")
        self.assertNotContains(response, "admin-verification-icon--unverified")
        self.assertNotContains(response, "Hacer staff")
        self.assertNotContains(response, "Quitar staff")

    def test_users_table_orders_by_joined_date_newest_first(self):
        older_user = User.objects.create_user(
            email="older@example.com",
            password="ignored",
            is_active=True,
        )
        newer_user = User.objects.create_user(
            email="newer@example.com",
            password="ignored",
            is_active=True,
        )
        User.objects.filter(pk=older_user.pk).update(
            date_joined=timezone.now() - timezone.timedelta(days=2)
        )
        User.objects.filter(pk=newer_user.pk).update(date_joined=timezone.now())
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"))

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response.content.index(b"newer@example.com"),
            response.content.index(b"older@example.com"),
        )

    def test_users_search_filters_by_phone_number(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="ignored",
            is_active=True,
        )
        UserVerification.objects.create(
            user=self.user,
            phone_country_code="+593",
            phone_number="987654321",
        )
        UserVerification.objects.create(
            user=other_user,
            phone_country_code="+593",
            phone_number="111222333",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"), {"q": "987654321"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "user@example.com")
        self.assertNotContains(response, "other@example.com")

    def test_users_status_filter_shows_only_active(self):
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="ignored",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"), {"visibility": "active"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_visibility"], "active")
        self.assertTrue(response.context["has_filters"])
        self.assertContains(response, "admin@example.com")
        self.assertContains(response, "user@example.com")
        self.assertNotContains(response, inactive_user.email)

    def test_users_status_filter_shows_only_inactive(self):
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="ignored",
            is_active=False,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("adminapp:users"),
            {"visibility": "inactive"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_visibility"], "inactive")
        self.assertTrue(response.context["has_filters"])
        self.assertContains(response, inactive_user.email)
        self.assertNotContains(response, "admin@example.com")
        self.assertNotContains(response, "user@example.com")

    def test_users_table_shows_status_last_login_and_listings_count(self):
        category = Category.objects.create(name="Admin QA", slug="admin-qa")
        Listing.objects.create(
            title="User listing",
            description="Listing created for admin table tests.",
            price_amount="10.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        last_login = timezone.now() - timezone.timedelta(hours=3)
        User.objects.filter(pk=self.user.pk).update(
            is_active=False,
            last_login=last_login,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Estado", response.context["user_table_headers"])
        self.assertIn("Último acceso", response.context["user_table_headers"])
        self.assertIn("Anuncios", response.context["user_table_headers"])
        listed_user = next(
            user for user in response.context["users"] if user.pk == self.user.pk
        )
        self.assertEqual(listed_user.listings_count, 1)
        self.assertContains(response, 'aria-label="Activar usuario user@example.com"')
        self.assertContains(response, 'aria-checked="false"')
        self.assertContains(
            response,
            date_filter(timezone.localtime(last_login), "Y-m-d H:i"),
        )

    def test_staff_can_delete_user_from_users_table(self):
        victim = User.objects.create_user(
            email="delete-me@example.com",
            password="ignored",
            is_active=True,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:user_delete", kwargs={"pk": victim.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertFalse(User.objects.filter(pk=victim.pk).exists())

    def test_staff_cannot_delete_current_user_from_users_table(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:user_delete", kwargs={"pk": self.admin.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertContains(response, "No puedes eliminar tu propio usuario")

    def test_users_table_confirms_active_listings_when_deactivating_user(self):
        category = Category.objects.create(name="Admin status", slug="admin-status")
        Listing.objects.create(
            title="Visible listing",
            description="Listing that should be mentioned in the confirmation.",
            price_amount="10.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("adminapp:users"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Desactivar usuario user@example.com"')
        self.assertContains(response, "Se ocultarán 1 anuncio activo")
        self.assertContains(response, "Tiene 1 anuncio activo asociado")

    def test_staff_can_deactivate_user_and_archive_published_listings(self):
        category = Category.objects.create(
            name="Admin deactivate",
            slug="admin-deactivate",
        )
        active_listing = Listing.objects.create(
            title="Active listing",
            description="Listing that should be archived when user is deactivated.",
            price_amount="10.00",
            seller=self.user,
            category=category,
            status=Listing.Status.PUBLISHED,
        )
        hidden_listing = Listing.objects.create(
            title="Hidden listing",
            description="Listing that should remain hidden.",
            price_amount="20.00",
            seller=self.user,
            category=category,
            status=Listing.Status.ARCHIVED,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:user_toggle_active", kwargs={"pk": self.user.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        active_listing.refresh_from_db()
        hidden_listing.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(active_listing.status, Listing.Status.ARCHIVED)
        self.assertEqual(hidden_listing.status, Listing.Status.ARCHIVED)
        self.assertContains(response, 'aria-label="Activar usuario user@example.com"')
        self.assertContains(response, 'aria-checked="false"')

    def test_reactivating_user_does_not_republish_archived_listings(self):
        category = Category.objects.create(
            name="Admin reactivate",
            slug="admin-reactivate",
        )
        listing = Listing.objects.create(
            title="Archived listing",
            description="Listing that should remain archived after reactivation.",
            price_amount="10.00",
            seller=self.user,
            category=category,
            status=Listing.Status.ARCHIVED,
        )
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:user_toggle_active", kwargs={"pk": self.user.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        listing.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(listing.status, Listing.Status.ARCHIVED)
        self.assertContains(response, 'aria-label="Desactivar usuario user@example.com"')
        self.assertContains(response, 'aria-checked="true"')

    def test_staff_cannot_deactivate_current_user_from_users_table(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("adminapp:user_toggle_active", kwargs={"pk": self.admin.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertContains(response, "No puedes desactivar tu propio usuario")
