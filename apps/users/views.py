from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LogoutView
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.views import View

from django_htmx.http import HttpResponseClientRedirect

from apps.listings.models import ListingLead
from apps.listings.services import user_listings_queryset
from apps.listings.views import (
    create_listing_base,
    create_listing_in_category,
    listing_edit,
)
from apps.trust.services import seller_trust_bundle
from apps.core.constants import COUNTRY_PHONE_CODES

from .forms import (
    ContactPreferenceForm,
    PhoneVerificationForm,
    RegisterStepOneForm,
    RegisterStepTwoForm,
    UserCreationForm,
)
from .models import USER_EMAIL_MAX_LENGTH, UserVerification
from .otp_auth import normalize_email, request_otp_for_user, request_user_otp, verify_user_otp


USER_OTP_GENERIC_MESSAGE = "Si la cuenta existe, recibirás un código de acceso."


class RegisterView(View):
    template_name = "users/register.html"
    success_url = reverse_lazy("users:account")
    session_key = "register_step1"
    otp_user_session_key = "signup_otp_user_id"
    otp_email_session_key = "signup_otp_email"

    def get(self, request):
        # Initial load always shows Step 1 (SSR). Non-HTMX fallback is provided via <noscript>.
        return render(
            request,
            self.template_name,
            {
                "step1_form": RegisterStepOneForm(),
                "country_phone_codes": COUNTRY_PHONE_CODES,
                "full_form": UserCreationForm(),
            },
        )

    def post(self, request):
        step = (request.POST.get("step") or "").strip()
        is_htmx = bool(getattr(request, "htmx", False))

        if step == "1":
            step1_form = RegisterStepOneForm(request.POST)
            if step1_form.is_valid():
                request.session[self.session_key] = {
                    "email": step1_form.cleaned_data["email"],
                    "first_name": step1_form.cleaned_data["first_name"],
                    "last_name": step1_form.cleaned_data["last_name"],
                }
                request.session.modified = True

                if is_htmx:
                    step2_form = RegisterStepTwoForm(
                        initial={"phone_country_code": "+593"},
                        profile=request.session.get(self.session_key, {}),
                    )
                    return render(
                        request,
                        "users/partials/register_step2.html",
                        {
                            "step2_form": step2_form,
                            "country_phone_codes": COUNTRY_PHONE_CODES,
                        },
                    )

                # Fallback: show full form in one page.
                full_form = UserCreationForm(initial=request.session.get(self.session_key, {}))
                return render(
                    request,
                    self.template_name,
                    {
                        "step1_form": step1_form,
                        "country_phone_codes": COUNTRY_PHONE_CODES,
                        "full_form": full_form,
                    },
                )

            if is_htmx:
                return render(
                    request,
                    "users/partials/register_step1.html",
                    {"step1_form": step1_form},
                )
            return render(
                request,
                self.template_name,
                {
                    "step1_form": step1_form,
                    "country_phone_codes": COUNTRY_PHONE_CODES,
                    "full_form": UserCreationForm(),
                },
            )

        if step == "2":
            step1_data = request.session.get(self.session_key) or {}
            if not step1_data:
                messages.info(
                    request,
                    "Tu registro expiró. Vuelve a ingresar tu correo para continuar.",
                )
                if is_htmx:
                    return HttpResponseClientRedirect(reverse("users:register"))
                return redirect("users:register")

            step2_form = RegisterStepTwoForm(
                request.POST,
                profile=step1_data,
            )
            if not step2_form.is_valid():
                if is_htmx:
                    return render(
                        request,
                        "users/partials/register_step2.html",
                        {
                            "step2_form": step2_form,
                            "country_phone_codes": COUNTRY_PHONE_CODES,
                        },
                    )
                # Misma UI que HTMX: seguir en paso 2 con errores visibles (no volver al paso 1).
                return render(
                    request,
                    self.template_name,
                    {
                        "step1_form": RegisterStepOneForm(initial=step1_data),
                        "step2_form": step2_form,
                        "country_phone_codes": COUNTRY_PHONE_CODES,
                        "full_form": UserCreationForm(
                            {**step1_data, **request.POST.dict()}
                        ),
                    },
                )

            combined_data = {
                **step1_data,
                "phone_country_code": step2_form.cleaned_data["phone_country_code"],
                "phone_number": step2_form.cleaned_data["phone_number"],
                "accept_terms": step2_form.cleaned_data["accept_terms"],
            }

            full_form = UserCreationForm(combined_data)
            if not full_form.is_valid():
                # UserCreationForm (p. ej. email duplicado) es la fuente de verdad.
                for field_name, errs in full_form.errors.items():
                    if field_name == "email":
                        # Normaliza el copy del caso "email duplicado" (race condition / bypass Step 1).
                        step2_form.add_error(
                            None, "Ya existe una cuenta con ese correo electrónico."
                        )
                        continue
                    if field_name in step2_form.fields:
                        step2_form.add_error(field_name, errs)
                    else:
                        step2_form.add_error(None, errs)
                if is_htmx:
                    return render(
                        request,
                        "users/partials/register_step2.html",
                        {
                            "step2_form": step2_form,
                            "country_phone_codes": COUNTRY_PHONE_CODES,
                        },
                    )
                return render(
                    request,
                    self.template_name,
                    {
                        "step1_form": RegisterStepOneForm(initial=step1_data),
                        "step2_form": step2_form,
                        "country_phone_codes": COUNTRY_PHONE_CODES,
                        "full_form": full_form,
                    },
                )

            user = full_form.save(commit=False)
            user.is_active = False
            user.save()
            verification, _ = UserVerification.objects.get_or_create(user=user)
            verification.phone_country_code = full_form.cleaned_data.get("phone_country_code", "+593")
            verification.phone_number = full_form.cleaned_data.get("phone_number", "")
            verification.save(update_fields=["phone_country_code", "phone_number"])

            request.session.pop(self.session_key, None)
            otp_result = request_otp_for_user(user)
            request.session[self.otp_user_session_key] = user.pk
            request.session[self.otp_email_session_key] = otp_result.email or user.email
            request.session.modified = True

            if otp_result.sent:
                messages.success(
                    request,
                    "Creamos tu cuenta. Te enviamos un código para confirmarla.",
                )
            else:
                _add_user_otp_request_message(request, otp_result)

            next_url = reverse("users:register_verify")
            if request.htmx:
                return HttpResponseClientRedirect(next_url)
            return redirect(next_url)

        return HttpResponseBadRequest("Invalid step")


def _clear_signup_otp_session(request):
    request.session.pop(RegisterView.otp_user_session_key, None)
    request.session.pop(RegisterView.otp_email_session_key, None)
    request.session.modified = True


def _clear_user_otp_session(request):
    request.session.pop("user_otp_user_id", None)
    request.session.pop("user_otp_email", None)
    request.session.pop("user_otp_next", None)
    request.session.modified = True


def _posted_otp_code(request):
    raw_code = request.POST.get("code") or "".join(request.POST.getlist("code_digits"))
    return "".join(char for char in raw_code if char.isdigit())[:6]


def _add_user_otp_request_message(request, result):
    if result.reason == "sent":
        messages.success(
            request,
            "Enviamos un nuevo código. Revisa tu correo y usa el más reciente.",
        )
    elif result.reason == "invalid_user":
        messages.info(
            request,
            (
                "Si la cuenta existe, intentamos enviar un código de acceso. "
                "Revisa tu correo antes de pedir otro."
            ),
        )
    elif result.reason == "resend_cooldown":
        messages.warning(
            request,
            (
                "Espera "
                f"{settings.USER_OTP_RESEND_COOLDOWN_SECONDS} segundos antes de "
                "pedir otro código. Revisa el último correo que te enviamos."
            ),
        )
    elif result.reason == "send_limit":
        messages.error(
            request,
            (
                "Llegaste al límite de códigos por ahora. Espera unos minutos "
                "antes de intentarlo de nuevo."
            ),
        )
    elif result.reason == "attempt_cooldown":
        messages.error(
            request,
            (
                "Por seguridad bloqueamos temporalmente nuevos códigos tras "
                "varios intentos fallidos. Intenta nuevamente en unos minutos."
            ),
        )


def _add_user_otp_verify_message(request, result):
    if result.reason == "expired":
        messages.error(request, "El código venció. Solicita uno nuevo para continuar.")
    elif result.reason == "max_attempts":
        messages.error(
            request,
            (
                "Demasiados intentos incorrectos. Por seguridad, solicita un "
                "nuevo código en unos minutos."
            ),
        )
    else:
        messages.error(
            request,
            "Código incorrecto. Revisa los 6 dígitos e inténtalo de nuevo.",
        )


def _signup_otp_context(request):
    return {
        "otp_email": request.session.get(RegisterView.otp_email_session_key, ""),
        "user_email_max_length": USER_EMAIL_MAX_LENGTH,
    }


def _login_context(request, *, step=None, email="", next_url=""):
    session_email = request.session.get("user_otp_email", "")
    return {
        "login_step": step or ("code" if session_email else "email"),
        "otp_email": email or session_email,
        "otp_next": next_url or request.session.get("user_otp_next", ""),
        "otp_generic_message": USER_OTP_GENERIC_MESSAGE,
        "user_email_max_length": USER_EMAIL_MAX_LENGTH,
    }


def _is_safe_next_url(request, next_url: str) -> bool:
    return bool(next_url) and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


def _default_post_login_url(user) -> str:
    if user.is_staff or user.is_superuser:
        return reverse("adminapp:dashboard")
    return reverse("users:account")


def _is_admin_user(user) -> bool:
    return user.is_staff or user.is_superuser


def _admin_panel_redirect(request):
    messages.info(request, "Los administradores deben usar el panel de administración.")
    return redirect("adminapp:dashboard")


def _resolve_post_login_url(request, user, next_url: str = "") -> str:
    if _is_safe_next_url(request, next_url):
        return next_url
    return _default_post_login_url(user)


def register_verify_view(request):
    user_id = request.session.get(RegisterView.otp_user_session_key)
    email = request.session.get(RegisterView.otp_email_session_key, "")
    if not user_id or not email:
        messages.info(request, "Empieza el registro para recibir tu código de confirmación.")
        return redirect("users:register")

    if request.user.is_authenticated:
        _clear_signup_otp_session(request)
        return redirect(_resolve_post_login_url(request, request.user))

    if request.method == "GET":
        return render(request, "users/register_verify.html", _signup_otp_context(request))

    action = request.POST.get("action") or "verify_code"
    user = get_object_or_404(get_user_model(), pk=user_id, email__iexact=email)

    if action == "request_code":
        result = request_otp_for_user(user, email)
        _add_user_otp_request_message(request, result)
        return render(request, "users/register_verify.html", _signup_otp_context(request))

    if action == "verify_code":
        result = verify_user_otp(
            user_id,
            email,
            _posted_otp_code(request),
            allow_inactive=True,
        )
        if result.success:
            if not result.user.is_active:
                result.user.is_active = True
                result.user.save(update_fields=["is_active"])
            login(request, result.user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.set_expiry(settings.USER_OTP_SESSION_AGE)
            _clear_signup_otp_session(request)
            return redirect("users:account")

        _add_user_otp_verify_message(request, result)
        return render(request, "users/register_verify.html", _signup_otp_context(request))

    return redirect("users:register_verify")


def email_login_view(request):
    if request.user.is_authenticated:
        next_url = (request.GET.get("next") or "").strip()
        return redirect(_resolve_post_login_url(request, request.user, next_url))

    if request.method == "GET":
        next_url = (request.GET.get("next") or "").strip()
        _clear_user_otp_session(request)
        if next_url:
            request.session["user_otp_next"] = next_url
            request.session.modified = True
        return render(
            request,
            "users/login.html",
            _login_context(request, next_url=next_url),
        )

    action = request.POST.get("action") or "request_code"
    if action == "change_email":
        _clear_user_otp_session(request)
        return render(
            request,
            "users/login.html",
            _login_context(request, step="email"),
        )

    if action == "request_code":
        next_url = (
            request.POST.get("next") or request.session.get("user_otp_next") or ""
        ).strip()
        email = normalize_email(
            request.POST.get("email") or request.session.get("user_otp_email") or ""
        )
        result = request_user_otp(email)
        request.session["user_otp_email"] = result.email or email
        if next_url:
            request.session["user_otp_next"] = next_url
        if result.user_id:
            request.session["user_otp_user_id"] = result.user_id
        else:
            request.session.pop("user_otp_user_id", None)
        request.session.modified = True
        _add_user_otp_request_message(request, result)
        return render(
            request,
            "users/login.html",
            _login_context(
                request,
                step="code",
                email=result.email or email,
                next_url=next_url,
            ),
        )

    if action == "verify_code":
        result = verify_user_otp(
            request.session.get("user_otp_user_id"),
            request.session.get("user_otp_email", ""),
            _posted_otp_code(request),
        )
        if result.success:
            next_url = request.session.get("user_otp_next") or ""
            login(request, result.user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.set_expiry(settings.USER_OTP_SESSION_AGE)
            _clear_user_otp_session(request)
            return redirect(
                resolve_url(_resolve_post_login_url(request, result.user, next_url))
            )
        _add_user_otp_verify_message(request, result)
        return render(request, "users/login.html", _login_context(request, step="code"))

    return redirect(reverse("users:login"))


class EmailLogoutView(LogoutView):
    next_page = reverse_lazy("root_home")


_ACCOUNT_SECTION_TITLES = {
    "overview": "Mi cuenta",
    "listings": "Mis anuncios",
    "leads": "Contactos recibidos",
    "create": "Crear anuncio",
}


@login_required
def account_dashboard(request, section="overview"):
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)

    allowed = {"overview", "listings", "leads"}
    if section not in allowed:
        section = "overview"

    User = get_user_model()
    user = User.objects.get(pk=request.user.pk)
    verification, _ = UserVerification.objects.get_or_create(user=user)
    phone_verified = bool(verification.phone_verified)
    contact_preference_form = ContactPreferenceForm(instance=verification)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action != "contact_preferences":
            return HttpResponseBadRequest("Invalid action")
        contact_preference_form = ContactPreferenceForm(request.POST, instance=verification)
        if contact_preference_form.is_valid():
            contact_preference_form.save()
            return redirect("users:account")
        messages.error(request, "No pudimos actualizar tu preferencia. Intenta nuevamente.")

    context = {
        "account_user": user,
        "verification": verification,
        "contact_preference_form": contact_preference_form,
        "phone_verified": phone_verified,
        "section": section,
        "account_page_title": _ACCOUNT_SECTION_TITLES[section],
        "page_obj": None,
    }

    if section == "listings":
        qs = user_listings_queryset(user)
        listings_q = (request.GET.get("q") or "").strip()
        context["listings_q"] = listings_q
        if listings_q:
            qs = qs.filter(
                Q(title__icontains=listings_q)
                | Q(description__icontains=listings_q)
                | Q(location__icontains=listings_q)
            )
        paginator = Paginator(qs, 20)
        context["page_obj"] = paginator.get_page(request.GET.get("page") or 1)

    if section == "leads":
        qs = (
            ListingLead.objects.filter(seller=user)
            .select_related("listing", "buyer_user")
            .order_by("-created_at")
        )
        leads_q = (request.GET.get("q") or "").strip()
        context["leads_q"] = leads_q
        if leads_q:
            qs = qs.filter(
                Q(listing__title__icontains=leads_q)
                | Q(buyer_name__icontains=leads_q)
                | Q(buyer_email__icontains=leads_q)
                | Q(message__icontains=leads_q)
            )
        paginator = Paginator(qs, 20)
        context["page_obj"] = paginator.get_page(request.GET.get("page") or 1)

    if getattr(request, "htmx", False):
        return render(request, "users/partials/account_main.html", context)

    return render(request, "users/account_dashboard.html", context)


@login_required
def listing_edit_dashboard(request, slug):
    """Editar anuncio dentro del panel Mi cuenta (ruta en español)."""
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)
    return listing_edit(request, slug, account_dashboard=True)


@login_required
def listing_create_dashboard(request):
    """Selector de tipo de publicación (Mi cuenta)."""
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)
    return create_listing_base(request, account_dashboard=True)


@login_required
def listing_publish_in_category_dashboard(request, category_slug):
    """Publicar en /mi-cuenta/publicar/<categoría>/."""
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)
    return create_listing_in_category(
        request,
        category_slug,
        account_dashboard=True,
    )


def profile_detail(request, pk):
    user = get_object_or_404(
        get_user_model().objects.select_related("verification"),
        pk=pk,
        is_active=True,
    )
    trust = seller_trust_bundle(user)
    return render(
        request,
        "users/profile_detail.html",
        {"profile_user": user, "seller_trust": trust},
    )


@login_required
def verify_phone(request):
    profile, _ = UserVerification.objects.get_or_create(user=request.user)
    if profile.phone_verified:
        messages.info(request, "Tu teléfono ya está verificado.")
        return redirect("users:account")

    next_url = (request.GET.get("next") or request.POST.get("next") or "").strip()

    if request.method == "POST":
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            profile.phone_number = form.cleaned_data["phone_number"]
            profile.phone_verified = True
            profile.verification_date = timezone.now()
            profile.save(update_fields=["phone_number", "phone_verified", "verification_date"])
            messages.success(request, "Tu número de teléfono está verificado.")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect("users:account")
    else:
        form = PhoneVerificationForm(
            initial={"phone_number": profile.phone_number or ""}
        )

    return render(
        request,
        "users/verify_phone.html",
        {"form": form, "next_url": next_url},
    )
