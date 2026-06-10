from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.categories.models import Category

from .forms import RegisterStepOneForm, UserCreationForm
from .models import User, UserLoginOTP, UserVerification
from .otp_auth import request_user_otp


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class UserPasswordlessAuthTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def _user(self, email="user@example.com", **kwargs):
        defaults = {
            "first_name": "User",
            "last_name": "Example",
            "is_active": True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(email=email, password="ignored", **defaults)

    def _request_code(self, email="user@example.com", code="123456"):
        with patch("apps.users.otp_auth.generate_user_otp_code", return_value=code):
            return self.client.post(
                reverse("users:login"),
                {"action": "request_code", "email": email},
            )

    def test_register_creates_user_without_usable_password(self):
        step1 = {
            "step": "1",
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "User",
        }
        self.client.post(reverse("users:register"), step1)
        response = self.client.post(
            reverse("users:register"),
            {
                "step": "2",
                "phone_country_code": "+593",
                "phone_number": "987654321",
                "accept_terms": "on",
            },
        )

        self.assertRedirects(response, reverse("users:account"))
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.has_usable_password())
        verification = UserVerification.objects.get(user=user)
        self.assertEqual(verification.phone_number, "987654321")

    def test_signup_form_limits_match_ui_constraints(self):
        step1_form = RegisterStepOneForm()
        full_form = UserCreationForm()

        self.assertEqual(User._meta.get_field("first_name").max_length, 25)
        self.assertEqual(User._meta.get_field("last_name").max_length, 25)
        self.assertEqual(User._meta.get_field("email").max_length, 255)
        self.assertEqual(step1_form.fields["first_name"].max_length, 25)
        self.assertEqual(step1_form.fields["last_name"].max_length, 25)
        self.assertEqual(step1_form.fields["email"].max_length, 255)
        self.assertEqual(full_form.fields["first_name"].max_length, 25)
        self.assertEqual(full_form.fields["last_name"].max_length, 25)
        self.assertEqual(full_form.fields["email"].max_length, 255)
        self.assertEqual(step1_form.fields["first_name"].widget.attrs["maxlength"], "25")
        self.assertEqual(step1_form.fields["last_name"].widget.attrs["maxlength"], "25")
        self.assertEqual(step1_form.fields["email"].widget.attrs["maxlength"], "255")
        self.assertEqual(full_form.fields["first_name"].widget.attrs["maxlength"], "25")
        self.assertEqual(full_form.fields["last_name"].widget.attrs["maxlength"], "25")
        self.assertEqual(full_form.fields["email"].widget.attrs["maxlength"], "255")

    def test_register_rejects_overlong_signup_fields(self):
        form = RegisterStepOneForm(
            data={
                "email": f"{'a' * 246}@example.com",
                "first_name": "N" * 26,
                "last_name": "U" * 26,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()["email"][0].code, "max_length")
        self.assertEqual(form.errors.as_data()["first_name"][0].code, "max_length")
        self.assertEqual(form.errors.as_data()["last_name"][0].code, "max_length")

    def test_regular_user_receives_login_otp(self):
        self._user()
        response = self._request_code(code="482731")

        self.assertEqual(response.status_code, 200)
        otp = UserLoginOTP.objects.get()
        self.assertEqual(otp.email, "user@example.com")
        self.assertNotEqual(otp.code_hash, "482731")
        self.assertTrue(check_password("482731", otp.code_hash))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("482731", mail.outbox[0].body)

    def test_resend_before_cooldown_shows_clear_message(self):
        self._user()
        self._request_code(code="482731")
        response = self._request_code(code="193847")

        self.assertContains(response, "Espera 60 segundos")
        self.assertEqual(UserLoginOTP.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_changing_email_repeatedly_does_not_send_codes(self):
        self._user()
        self._request_code(code="482731")
        mail.outbox = []

        for _ in range(5):
            response = self.client.post(
                reverse("users:login"),
                {"action": "change_email"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Correo electrónico")
        self.assertEqual(UserLoginOTP.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn("user_otp_email", self.client.session)
        self.assertNotIn("user_otp_user_id", self.client.session)

    def test_login_get_clears_pending_code_step(self):
        self._user()
        self._request_code(code="482731")

        response = self.client.get(reverse("users:login"))

        self.assertEqual(response.context["login_step"], "email")
        self.assertContains(response, "Correo electrónico")
        self.assertNotIn("user_otp_email", self.client.session)
        self.assertNotIn("user_otp_user_id", self.client.session)

    def test_send_limit_blocks_multiple_codes_in_window(self):
        self._user()
        with patch("apps.users.otp_auth.send_user_otp_email"):
            for _ in range(settings.USER_OTP_SEND_LIMIT):
                result = request_user_otp("user@example.com")
                self.assertEqual(result.reason, "sent")
                UserLoginOTP.objects.filter(
                    pk=UserLoginOTP.objects.latest("pk").pk
                ).update(
                    created_at=timezone.now()
                    - timezone.timedelta(seconds=settings.USER_OTP_RESEND_COOLDOWN_SECONDS + 1)
                )
            blocked = request_user_otp("user@example.com")

        self.assertEqual(blocked.reason, "send_limit")
        self.assertEqual(UserLoginOTP.objects.count(), settings.USER_OTP_SEND_LIMIT)

    def test_unknown_user_gets_generic_message_without_otp(self):
        response = self.client.post(
            reverse("users:login"),
            {"action": "request_code", "email": "missing@example.com"},
        )

        self.assertContains(response, "Si la cuenta existe")
        self.assertContains(response, "intentamos enviar un código de acceso")
        self.assertContains(response, "<strong>missing@example.com</strong>", html=True)
        self.assertEqual(UserLoginOTP.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_staff_user_receives_login_otp_and_redirects_to_admin(self):
        User.objects.create_user(
            email="admin@example.com",
            password="ignored",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        with patch("apps.users.otp_auth.generate_user_otp_code", return_value="482731"):
            response = self.client.post(
                reverse("users:login"),
                {"action": "request_code", "email": "admin@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserLoginOTP.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

        verify_response = self.client.post(
            reverse("users:login"),
            {"action": "verify_code", "code": "482731"},
        )
        self.assertRedirects(verify_response, reverse("adminapp:dashboard"))

    def test_valid_code_logs_in_with_django_session(self):
        user = self._user()
        self._request_code(code="123456")
        response = self.client.post(
            reverse("users:login"),
            {"action": "verify_code", "code": "123456"},
        )

        self.assertRedirects(response, reverse("users:account"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(
            self.client.session.get_expiry_age(),
            settings.USER_OTP_SESSION_AGE,
        )

    def test_segmented_code_digits_log_user_in(self):
        user = self._user()
        self._request_code(code="654321")
        response = self.client.post(
            reverse("users:login"),
            {"action": "verify_code", "code_digits": ["6", "5", "4", "3", "2", "1"]},
        )

        self.assertRedirects(response, reverse("users:account"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_posting_password_to_login_does_not_authenticate(self):
        self._user()
        response = self.client.post(
            reverse("users:login"),
            {"username": "user@example.com", "password": "ignored"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_legacy_password_reset_routes_redirect_to_login(self):
        response = self.client.get("/accounts/password-reset/")
        self.assertRedirects(
            response,
            "/ingresar/",
            status_code=301,
            target_status_code=200,
        )


class AdminAccountAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="staff-account@example.com",
            password="ignored",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        cls.category = Category.objects.create(name="Hogar", slug="hogar")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_staff_account_redirects_to_admin_panel(self):
        response = self.client.get(reverse("users:account"))

        self.assertRedirects(response, reverse("adminapp:dashboard"))

    def test_staff_nav_points_to_admin_panel(self):
        response = self.client.get(reverse("root_home"))

        self.assertContains(response, 'href="/admin/"')
        self.assertContains(response, 'aria-label="Panel admin"')
        self.assertNotContains(response, 'aria-label="Mi cuenta"')

    def test_staff_account_listings_redirects_to_admin_panel(self):
        response = self.client.get(reverse("users:account_listings"))

        self.assertRedirects(response, reverse("adminapp:dashboard"))

    def test_staff_account_publish_redirects_to_admin_panel(self):
        response = self.client.get(reverse("users:account_publish"))

        self.assertRedirects(response, reverse("adminapp:dashboard"))

    def test_staff_account_publish_category_redirects_to_admin_panel(self):
        response = self.client.get(
            reverse(
                "users:account_publish_in_category",
                kwargs={"category_slug": self.category.slug},
            )
        )

        self.assertRedirects(response, reverse("adminapp:dashboard"))
