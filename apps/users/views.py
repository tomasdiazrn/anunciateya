from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.views import View

from apps.listings.services import user_listings_queryset
from apps.listings.views import (
    create_listing_base,
    create_listing_in_category,
    listing_edit,
)
from apps.trust.services import seller_trust_bundle
from apps.core.constants import COUNTRY_PHONE_CODES

from .forms import (
    AccountPasswordChangeForm,
    EmailAuthenticationForm,
    PhoneVerificationForm,
    RegisterStepOneForm,
    RegisterStepTwoForm,
    UserCreationForm,
)
from .models import UserVerification


class RegisterView(View):
    template_name = "users/register.html"
    success_url = reverse_lazy("listings:list")
    session_key = "register_step1"

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
                if is_htmx:
                    step1_form = RegisterStepOneForm()
                    return render(
                        request,
                        "users/partials/register_step1.html",
                        {"step1_form": step1_form},
                    )
                return redirect("users:register")

            step2_form = RegisterStepTwoForm(request.POST)
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
                # Fallback: show full form
                combined = {**step1_data, **request.POST}
                full_form = UserCreationForm(combined)
                return render(
                    request,
                    self.template_name,
                    {
                        "step1_form": RegisterStepOneForm(initial=step1_data),
                        "country_phone_codes": COUNTRY_PHONE_CODES,
                        "full_form": full_form,
                    },
                )

            combined_data = {
                **step1_data,
                "phone_country_code": step2_form.cleaned_data["phone_country_code"],
                "phone_number": step2_form.cleaned_data["phone_number"],
                "password1": step2_form.cleaned_data["password1"],
                "password2": step2_form.cleaned_data["password2"],
                "accept_terms": step2_form.cleaned_data["accept_terms"],
            }

            full_form = UserCreationForm(combined_data)
            if not full_form.is_valid():
                # Normally shouldn't happen (step validations), but keep Django form as source of truth.
                if is_htmx:
                    # Map errors to step2 UI by reusing step2_form + attaching non-field errors.
                    for field_name, errs in full_form.errors.items():
                        if field_name in step2_form.fields:
                            step2_form.add_error(field_name, errs)
                        else:
                            step2_form.add_error(None, errs)
                    return render(
                        request,
                        "users/partials/register_step2.html",
                        {"step2_form": step2_form, "country_phone_codes": COUNTRY_PHONE_CODES},
                    )
                return render(
                    request,
                    self.template_name,
                    {
                        "step1_form": RegisterStepOneForm(initial=step1_data),
                        "country_phone_codes": COUNTRY_PHONE_CODES,
                        "full_form": full_form,
                    },
                )

            user = full_form.save()
            verification, _ = UserVerification.objects.get_or_create(user=user)
            verification.phone_country_code = full_form.cleaned_data.get("phone_country_code", "+593")
            verification.phone_number = full_form.cleaned_data.get("phone_number", "")
            verification.save(update_fields=["phone_country_code", "phone_number"])

            request.session.pop(self.session_key, None)
            request.session.modified = True

            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(self.success_url)

        return HttpResponseBadRequest("Invalid step")


class EmailLoginView(LoginView):
    form_class = EmailAuthenticationForm
    template_name = "users/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return reverse("adminapp:dashboard")
        return super().get_default_redirect_url()


class EmailLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")


class EmailPasswordResetView(PasswordResetView):
    template_name = "users/password_reset_form.html"
    email_template_name = "users/emails/password_reset_email.txt"
    subject_template_name = "users/emails/password_reset_subject.txt"
    success_url = reverse_lazy("users:password_reset_done")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_name"] = settings.SITE_NAME
        return context


class EmailPasswordResetDoneView(PasswordResetDoneView):
    template_name = "users/password_reset_done.html"


class EmailPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "users/password_reset_confirm.html"
    success_url = reverse_lazy("users:password_reset_complete")


class EmailPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "users/password_reset_complete.html"


_ACCOUNT_SECTION_TITLES = {
    "overview": "Mi cuenta",
    "listings": "Mis anuncios",
    "create": "Crear anuncio",
}


class AccountPasswordChangeView(PasswordChangeView):
    form_class = AccountPasswordChangeForm
    template_name = "users/account_password_change.html"
    success_url = reverse_lazy("users:password_change_done")


class AccountPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "users/account_password_change_done.html"


@login_required
def account_dashboard(request, section="overview"):
    allowed = {"overview", "listings"}
    if section not in allowed:
        section = "overview"

    User = get_user_model()
    user = User.objects.get(pk=request.user.pk)
    verification, _ = UserVerification.objects.get_or_create(user=user)
    phone_verified = bool(verification.phone_verified)

    context = {
        "account_user": user,
        "verification": verification,
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

    if getattr(request, "htmx", False):
        return render(request, "users/partials/account_main.html", context)

    return render(request, "users/account_dashboard.html", context)


@login_required
def listing_edit_dashboard(request, slug):
    """Editar anuncio dentro del panel Mi cuenta (ruta en español)."""
    return listing_edit(request, slug, account_dashboard=True)


@login_required
def listing_create_dashboard(request):
    """Selector de tipo de publicación (Mi cuenta)."""
    return create_listing_base(request, account_dashboard=True)


@login_required
def listing_publish_in_category_dashboard(request, category_slug):
    """Publicar en /mi-cuenta/publicar/<categoría>/."""
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
