from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Avg, Count, Exists, OuterRef, ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.categories.models import Category
from apps.core.models import NewsletterSubscriber
from apps.listings import views as listing_publish_views
from apps.listings.models import Listing, ListingImage, ListingPromotion
from apps.trust.models import ListingReport
from apps.users.models import User, UserVerification

from .helpers import listing_search_q
from .hosting import build_renewal_url, get_hosting_membership

PAGE_SIZE = 20


def staff_required(view_func):
    """Authenticated staff only; others redirect to their account."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect(reverse("users:account"))
        return view_func(request, *args, **kwargs)

    return _wrapped


@require_http_methods(["GET"])
def admin_login_redirect(request):
    """Legacy admin login URL → unified OTP login with return path."""
    next_url = (request.GET.get("next") or "").strip() or reverse("adminapp:dashboard")
    query = urlencode({"next": next_url})
    return redirect(f"{reverse('users:login')}?{query}")


@require_POST
def admin_logout_view(request):
    logout(request)
    return redirect(reverse("root_home"))


def _filters_qs(request, exclude_page=True, extra=None):
    data = {}
    for key in request.GET.keys():
        if exclude_page and key == "page":
            continue
        val = request.GET.get(key)
        if val is not None and val != "":
            data[key] = val
    if extra:
        data.update(extra)
    return urlencode(data)


def _paginate(request, queryset, per_page=PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    page = request.GET.get("page", 1)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _listing_row_ctx(listing):
    return {
        "listing": listing,
    }


def _user_admin_queryset():
    return User.objects.select_related("verification").annotate(
        listings_count=Count("listings", distinct=True),
        active_listings_count=Count(
            "listings",
            filter=Q(listings__status=Listing.Status.PUBLISHED),
            distinct=True,
        ),
    )


def _user_row_ctx(user_obj, action_error=""):
    return {
        "user_obj": user_obj,
        "action_error": action_error,
    }


def _percentage(part, total):
    if not total:
        return 0
    return round((part / total) * 100)


@staff_required
def dashboard_view(request):
    now = timezone.now()
    since_7_days = now - timedelta(days=7)
    listings_url = reverse("adminapp:listings")
    newsletter_subscribers_url = reverse("adminapp:newsletter_subscribers")
    users_url = reverse("adminapp:users")

    listing_counts = Listing.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status=Listing.Status.PUBLISHED)),
        draft=Count("id", filter=Q(status=Listing.Status.DRAFT)),
        archived=Count("id", filter=Q(status=Listing.Status.ARCHIVED)),
        flagged=Count("id", filter=Q(is_flagged=True)),
    )
    users_total = User.objects.count()
    users_new_7_days = User.objects.filter(date_joined__gte=since_7_days).count()
    newsletter_active_total = NewsletterSubscriber.objects.filter(is_active=True).count()
    verified_users_total = UserVerification.objects.filter(phone_verified=True).count()
    active_promotions_total = ListingPromotion.objects.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gt=now,
    ).count()

    listing_images = ListingImage.objects.filter(listing_id=OuterRef("pk"))
    listings_without_images_total = (
        Listing.objects.annotate(has_images=Exists(listing_images))
        .filter(has_images=False)
        .count()
    )
    quality_average = Listing.objects.aggregate(avg=Avg("quality_score"))["avg"] or 0
    low_quality_threshold = 5.0

    attention_listings = (
        Listing.objects.select_related("seller", "category", "zone")
        .annotate(
            has_images=Exists(listing_images),
            reports_count=Count("reports", distinct=True),
        )
        .exclude(status=Listing.Status.ARCHIVED)
        .filter(
            Q(is_flagged=True)
            | Q(has_images=False)
            | Q(quality_score__lt=low_quality_threshold)
        )
        .order_by("-is_flagged", "has_images", "quality_score", "-updated_at")[:8]
    )

    context = {
        "admin_section": "dashboard",
        "admin_page_title": "Panel de administración",
        "dashboard_primary_cards": [
            {
                "label": "Publicados",
                "value": listing_counts["published"],
                "meta": (
                    f'{listing_counts["draft"]} borradores · '
                    f'{listing_counts["archived"]} archivados'
                ),
                "variant": "primary",
                "url": listings_url,
            },
            {
                "label": "Usuarios",
                "value": users_total,
                "meta": f"{users_new_7_days} nuevos en 7 días",
                "variant": "success",
                "url": users_url,
            },
            {
                "label": "Newsletter",
                "value": newsletter_active_total,
                "meta": "suscriptores activos",
                "variant": "neutral",
                "url": newsletter_subscribers_url,
            },
            {
                "label": "Reportados",
                "value": listing_counts["flagged"],
                "meta": f"{ListingReport.objects.filter(created_at__gte=since_7_days).count()} reportes en 7 días",
                "variant": "danger",
                "url": listings_url,
            },
        ],
        "dashboard_secondary_cards": [
            {
                "label": "Usuarios nuevos",
                "value": users_new_7_days,
                "meta": "últimos 7 días",
            },
            {
                "label": "Verificados",
                "value": verified_users_total,
                "meta": f"{_percentage(verified_users_total, users_total)}% de usuarios",
            },
            {
                "label": "Promociones activas",
                "value": active_promotions_total,
                "meta": "destacados e impulsos vigentes",
            },
            {
                "label": "Sin imágenes",
                "value": listings_without_images_total,
                "meta": "anuncios a completar",
            },
            {
                "label": "Calidad promedio",
                "value": f"{quality_average:.1f}",
                "meta": "score de anuncios",
            },
        ],
        "attention_listings": attention_listings,
        "low_quality_threshold": low_quality_threshold,
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "recent_listings": Listing.objects.select_related("seller", "category", "zone").order_by(
            "-created_at"
        )[:5],
        "recent_reports": ListingReport.objects.select_related(
            "listing",
            "reporter",
        ).order_by("-created_at")[:5],
        "listings_url": listings_url,
        "newsletter_subscribers_url": newsletter_subscribers_url,
        "users_url": users_url,
    }
    if request.htmx:
        return render(request, "adminapp/fragments/dashboard_main.html", context)
    return render(request, "adminapp/dashboard.html", context)


@staff_required
@require_http_methods(["GET"])
def hosting_view(request):
    context = {
        "admin_section": "hosting",
        "admin_page_title": "Hosting",
        "membership": get_hosting_membership(),
        "renewal_url": build_renewal_url(request),
    }
    template = (
        "adminapp/fragments/hosting_main.html"
        if request.htmx
        else "adminapp/hosting/detail.html"
    )
    return render(request, template, context)


@staff_required
@require_http_methods(["GET"])
def admin_listing_publish_view(request):
    return listing_publish_views.create_listing_base(
        request,
        admin_dashboard=True,
    )


@staff_required
def admin_listing_publish_in_category_view(request, category_slug):
    return listing_publish_views.create_listing_in_category(
        request,
        category_slug,
        admin_dashboard=True,
    )


@staff_required
@require_http_methods(["GET"])
def admin_listings_view(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    visibility = (request.GET.get("visibility") or "").strip()
    if visibility not in {"active", "inactive"}:
        visibility = ""

    qs = Listing.objects.select_related("seller", "category", "zone").order_by("-updated_at")
    if q:
        qs = qs.filter(listing_search_q(q))
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if visibility == "active":
        qs = qs.filter(status=Listing.Status.PUBLISHED)
    elif visibility == "inactive":
        qs = qs.exclude(status=Listing.Status.PUBLISHED)

    page_obj = _paginate(request, qs)
    filters_qs = _filters_qs(request, exclude_page=True)
    context = {
        "admin_section": "listings",
        "admin_page_title": "Anuncios",
        "listings": page_obj.object_list,
        "page_obj": page_obj,
        "search_q": q,
        "selected_category": category_slug,
        "selected_visibility": visibility,
        "category_options": Category.objects.all(),
        "visibility_options": [
            ("active", "Activos"),
            ("inactive", "Inactivos"),
        ],
        "has_filters": bool(q or category_slug or visibility),
        "filters_qs": filters_qs,
        "listings_clear_url": reverse("adminapp:listings"),
        "listing_publish_url": reverse("adminapp:listing_publish"),
        "listing_table_headers": [
            "Publicación",
            "Título",
            "Categoría",
            "Precio",
            "Usuario",
            "Reportado",
            "Estado",
            "Actualización",
            "Acciones",
        ],
    }
    template = (
        "adminapp/fragments/listings_main.html"
        if request.htmx
        else "adminapp/listings/list.html"
    )
    return render(request, template, context)


@staff_required
@require_http_methods(["GET"])
def admin_listing_detail_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.select_related("seller", "category", "zone"),
        pk=pk,
    )
    context = {
        "admin_section": "listings",
        "admin_page_title": f"Anuncio · {listing.title}",
        "listing": listing,
    }
    template = (
        "adminapp/fragments/listing_detail_main.html"
        if request.htmx
        else "adminapp/listings/detail.html"
    )
    return render(request, template, context)


@staff_required
@require_POST
def admin_listing_set_status(request, pk):
    try:
        listing = Listing.objects.select_related("seller", "category", "zone").get(pk=pk)
    except Listing.DoesNotExist:
        return HttpResponse("Anuncio no encontrado.", status=404)
    raw = (request.POST.get("status") or "").strip()
    valid = {
        Listing.Status.DRAFT,
        Listing.Status.PUBLISHED,
    }
    if raw not in valid:
        messages.error(request, "Estado no válido.")
    else:
        try:
            listing.status = raw
            listing.save(update_fields=["status", "updated_at"])
        except Exception:  # noqa: BLE001
            messages.error(request, "No se pudo cambiar el estado.")
    return render(request, "adminapp/listings/_row.html", _listing_row_ctx(listing))


@staff_required
@require_POST
def admin_listing_archive(request, pk):
    try:
        listing = Listing.objects.select_related("seller", "category", "zone").get(pk=pk)
    except Listing.DoesNotExist:
        return HttpResponse("Anuncio no encontrado.", status=404)
    try:
        listing.status = Listing.Status.ARCHIVED
        listing.save(update_fields=["status", "updated_at"])
    except Exception:  # noqa: BLE001
        messages.error(request, "No se pudo archivar el anuncio.")
    return render(request, "adminapp/listings/_row.html", _listing_row_ctx(listing))


@staff_required
@require_POST
def admin_listing_unarchive(request, pk):
    try:
        listing = Listing.objects.select_related("seller", "category", "zone").get(pk=pk)
    except Listing.DoesNotExist:
        return HttpResponse("Anuncio no encontrado.", status=404)
    try:
        listing.status = Listing.Status.DRAFT
        listing.save(update_fields=["status", "updated_at"])
    except Exception:  # noqa: BLE001
        messages.error(request, "No se pudo desarchivar el anuncio.")
    return render(request, "adminapp/listings/_row.html", _listing_row_ctx(listing))


@staff_required
@require_POST
def admin_listing_delete(request, pk):
    try:
        listing = Listing.objects.select_related("seller", "category", "zone").get(pk=pk)
    except Listing.DoesNotExist:
        return HttpResponse("Anuncio no encontrado.", status=404)

    try:
        listing.delete()
    except Exception:  # noqa: BLE001
        messages.error(request, "No se pudo eliminar el anuncio.")
        return render(request, "adminapp/listings/_row.html", _listing_row_ctx(listing))

    if request.htmx:
        return HttpResponse("")
    messages.success(request, "Anuncio eliminado.")
    return redirect(reverse("adminapp:listings"))


@staff_required
@require_http_methods(["GET"])
def admin_users_view(request):
    q = (request.GET.get("q") or "").strip()
    visibility = (request.GET.get("visibility") or "").strip()
    if visibility not in {"active", "inactive"}:
        visibility = ""

    qs = _user_admin_queryset().order_by("-date_joined")
    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(verification__phone_number__icontains=q)
        )
    if visibility == "active":
        qs = qs.filter(is_active=True)
    elif visibility == "inactive":
        qs = qs.filter(is_active=False)

    page_obj = _paginate(request, qs)
    filters_qs = _filters_qs(request, exclude_page=True)
    context = {
        "admin_section": "users",
        "admin_page_title": "Usuarios",
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "search_q": q,
        "selected_visibility": visibility,
        "visibility_options": [
            ("active", "Activos"),
            ("inactive", "Inactivos"),
        ],
        "has_filters": bool(q or visibility),
        "filters_qs": filters_qs,
        "users_clear_url": reverse("adminapp:users"),
        "user_table_headers": [
            "Se unió",
            "Email",
            "Nombre",
            "Teléfono",
            "Estado",
            "Último acceso",
            "Anuncios",
            "Acciones",
        ],
    }
    template = (
        "adminapp/fragments/users_main.html"
        if request.htmx
        else "adminapp/users/list.html"
    )
    return render(request, template, context)


@staff_required
@require_POST
def admin_user_delete_view(request, pk):
    user_obj = get_object_or_404(_user_admin_queryset(), pk=pk)
    if user_obj.pk == request.user.pk:
        deletion_error = "No puedes eliminar tu propio usuario desde esta sesión."
        if request.htmx:
            return render(
                request,
                "adminapp/users/_row.html",
                _user_row_ctx(user_obj, deletion_error),
            )
        messages.error(request, deletion_error)
        return redirect(reverse("adminapp:users"))

    user_label = user_obj.public_name
    try:
        user_obj.delete()
    except ProtectedError:
        deletion_error = (
            "No se puede eliminar este usuario porque tiene anuncios asociados."
        )
        if request.htmx:
            return render(
                request,
                "adminapp/users/_row.html",
                _user_row_ctx(user_obj, deletion_error),
            )
        messages.error(request, deletion_error)
        return redirect(reverse("adminapp:users"))

    if request.htmx:
        return HttpResponse("")
    messages.success(request, f"Usuario {user_label} eliminado.")
    return redirect(reverse("adminapp:users"))


@staff_required
@require_POST
def admin_user_toggle_active_view(request, pk):
    user_obj = get_object_or_404(_user_admin_queryset(), pk=pk)
    target_is_active = not user_obj.is_active

    if user_obj.pk == request.user.pk and not target_is_active:
        action_error = "No puedes desactivar tu propio usuario desde esta sesión."
        if request.htmx:
            return render(
                request,
                "adminapp/users/_row.html",
                _user_row_ctx(user_obj, action_error),
            )
        messages.error(request, action_error)
        return redirect(reverse("adminapp:users"))

    with transaction.atomic():
        user_obj.is_active = target_is_active
        user_obj.save(update_fields=["is_active"])

        if not target_is_active:
            Listing.objects.filter(
                seller=user_obj,
                status=Listing.Status.PUBLISHED,
            ).update(
                status=Listing.Status.ARCHIVED,
                updated_at=timezone.now(),
            )

    user_obj = get_object_or_404(_user_admin_queryset(), pk=pk)
    if request.htmx:
        return render(request, "adminapp/users/_row.html", _user_row_ctx(user_obj))

    status_label = "activado" if target_is_active else "desactivado"
    messages.success(request, f"Usuario {user_obj.public_name} {status_label}.")
    return redirect(reverse("adminapp:users"))


@staff_required
@require_http_methods(["GET"])
def admin_newsletter_subscribers_view(request):
    q = (request.GET.get("q") or "").strip()
    visibility = (request.GET.get("visibility") or "").strip()
    if visibility not in {"active", "inactive"}:
        visibility = ""

    qs = NewsletterSubscriber.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(email__icontains=q)
    if visibility == "active":
        qs = qs.filter(is_active=True)
    elif visibility == "inactive":
        qs = qs.filter(is_active=False)

    page_obj = _paginate(request, qs)
    filters_qs = _filters_qs(request, exclude_page=True)
    context = {
        "admin_section": "newsletter",
        "admin_page_title": "Newsletter",
        "subscribers": page_obj.object_list,
        "page_obj": page_obj,
        "search_q": q,
        "selected_visibility": visibility,
        "visibility_options": [
            ("active", "Activos"),
            ("inactive", "Inactivos"),
        ],
        "has_filters": bool(q or visibility),
        "filters_qs": filters_qs,
        "newsletter_clear_url": reverse("adminapp:newsletter_subscribers"),
        "subscriber_table_headers": [
            "Se suscribió",
            "Email",
            "Estado",
        ],
    }
    template = (
        "adminapp/fragments/newsletter_main.html"
        if request.htmx
        else "adminapp/newsletter/list.html"
    )
    return render(request, template, context)


@staff_required
@require_POST
def admin_newsletter_subscriber_toggle_active_view(request, pk):
    subscriber = get_object_or_404(NewsletterSubscriber, pk=pk)
    subscriber.is_active = not subscriber.is_active
    subscriber.save(update_fields=["is_active"])

    if request.htmx:
        return render(request, "adminapp/newsletter/_row.html", {"subscriber": subscriber})

    status_label = "activado" if subscriber.is_active else "desactivado"
    messages.success(request, f"Suscriptor {subscriber.email} {status_label}.")
    return redirect(reverse("adminapp:newsletter_subscribers"))


@staff_required
@require_http_methods(["GET"])
def admin_user_detail_view(request, pk):
    user_obj = get_object_or_404(User.objects.select_related("verification"), pk=pk)
    try:
        listings_count = Listing.objects.filter(seller=user_obj).count()
    except Exception:
        listings_count = None
    context = {
        "admin_section": "users",
        "admin_page_title": f"Usuario · {user_obj.email}",
        "user_obj": user_obj,
        "listings_count": listings_count,
    }
    template = (
        "adminapp/fragments/user_detail_main.html"
        if request.htmx
        else "adminapp/users/detail.html"
    )
    return render(request, template, context)
