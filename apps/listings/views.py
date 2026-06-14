import json
import mimetypes
import re
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.html import escape, strip_tags
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.categories.models import Category
from apps.categories.services import root_categories
from apps.trust.models import ListingReport
from apps.trust.services import bulk_seller_verification, seller_verification_bundle, sync_listing_flag
from apps.users.models import UserVerification

from .category_engine import (
    browse_category_canonical_redirect,
    build_category_page,
    vehicle_legacy_filter_canonical_redirect,
)
from .category_engine_queryplan import LISTING_DETAIL_ORM_PLAN, apply_query_plan
from .category_extensions import (
    ELECTRONICS_SLUG,
    EXTENSION_PUBLISH_META,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
    publish_flow_kind,
)
from .forms import (
    BaseListingForm,
    ElectronicsListingForm,
    HomeGoodsListingForm,
    ListingForm,
    ListingInterestForm,
    ListingReportForm,
    MotorcycleListingForm,
    PropertyListingForm,
    VehicleListingForm,
    DEFAULT_CONTACT_MESSAGE,
)
from .models import (
    ElectronicsListing,
    HomeGoodsListing,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)
from .market_taxonomy import (
    market_brand_queryset,
    market_model_queryset,
    scoped_brand_id_from_request_value,
)
from .listing_card_dto import build_listing_cards_for_listings
from .listing_detail_dto import build_listing_detail_context, listing_gallery_absolute_urls
from .services import (
    InterestSubmission,
    attach_listing_images,
    commit_listing_image_changes,
    validate_listing_image_changes,
    get_electronics_extension,
    get_homegoods_extension,
    get_motorcycle_extension,
    get_owned_listing,
    get_property_extension,
    get_vehicle_extension,
    MAX_LISTING_IMAGE_BYTES,
    MAX_LISTING_IMAGES,
    record_listing_interest,
    record_listing_whatsapp_lead,
    user_listings_queryset,
    validate_listing_image_uploads,
)
from .services_promotions import create_listing_promotion

# Legacy names (imports elsewhere may reference)
MAX_IMAGES = MAX_LISTING_IMAGES
MAX_IMAGE_BYTES = MAX_LISTING_IMAGE_BYTES
PRIVATE_PAGE_ROBOTS = "noindex, nofollow"


def _image_content_type_from_url(url: str) -> str:
    content_type, _encoding = mimetypes.guess_type(urlsplit(url).path)
    if content_type and content_type.startswith("image/"):
        return content_type
    return "image/jpeg"


def _is_listing_owner(request, listing):
    return request.user.is_authenticated and request.user.pk == listing.seller_id


def _is_listing_public(listing):
    return listing.status == Listing.Status.PUBLISHED


def _is_admin_user(user) -> bool:
    return user.is_staff or user.is_superuser


def _admin_panel_redirect(request):
    messages.info(request, "Los administradores deben usar el panel de administración.")
    return redirect("adminapp:dashboard")


def _render_listing_not_found(request):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "listings/listing_not_found.html",
        {
            "meta_title": f"Anuncio no disponible | {brand}",
            "meta_description": f"Este anuncio no está disponible en {brand}.",
        },
        status=404,
    )


def _contact_success_related_cards(listing, *, limit=3):
    rows_qs = (
        Listing.objects.published()
        .filter(category_id=listing.category_id)
        .exclude(pk=listing.pk)
    )
    rows_qs = apply_query_plan(rows_qs, LISTING_DETAIL_ORM_PLAN)
    rows = list(rows_qs.order_by("-created_at")[:limit])
    if not rows:
        return []
    seller_verification_map = bulk_seller_verification([row.seller_id for row in rows])
    return build_listing_cards_for_listings(
        rows,
        seller_verification_map=seller_verification_map,
        featured_top_ids=frozenset(),
    )


def _prune_json_ld(obj):
    """Quita claves None y dicts/listas vacíos del JSON-LD."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            pv = _prune_json_ld(v)
            if pv is None:
                continue
            if isinstance(pv, (dict, list)) and len(pv) == 0:
                continue
            out[k] = pv
        return out
    if isinstance(obj, list):
        out = [_prune_json_ld(x) for x in obj]
        out = [x for x in out if x is not None and not (isinstance(x, (dict, list)) and len(x) == 0)]
        return out
    return obj


def _property_place_json_ld(listing):
    if getattr(listing.category, "slug", "") != PROPERTY_SLUG:
        return None
    try:
        prop = listing.property
    except ObjectDoesNotExist:
        return None
    if (
        prop.location_precision != PropertyListing.LocationPrecision.EXACT
        or not (prop.address_line or "").strip()
    ):
        return None
    place = {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": (prop.address_line or "").strip(),
            "addressLocality": listing.zone.city if listing.zone_id else "",
        },
    }
    if prop.latitude is not None and prop.longitude is not None:
        place["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(prop.latitude),
            "longitude": float(prop.longitude),
        }
    if (prop.address_place_label or "").strip():
        place["name"] = prop.address_place_label.strip()
    return place


def _build_listing_json_ld(request, listing, trust):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    abs_listing = request.build_absolute_uri(listing.get_absolute_url())
    seller = listing.seller
    try:
        verification = seller.verification
    except ObjectDoesNotExist:
        verification = None
    show_seller_name = bool(getattr(verification, "show_name_in_listings", True))
    seller_url = ""
    seller_profile_links_enabled = getattr(
        settings,
        "USER_PUBLIC_PROFILE_LINKS_ENABLED",
        False,
    )
    if show_seller_name and seller_profile_links_enabled:
        seller_path = reverse("users:profile", kwargs={"pk": seller.pk})
        seller_url = request.build_absolute_uri(seller_path)

    image_urls = listing_gallery_absolute_urls(request, listing, limit=10)

    seller_name = "Vendedor"
    if show_seller_name:
        seller_name = (
            getattr(seller, "public_name", None)
            or seller.get_full_name()
            or "Vendedor"
        )
    seller_node = _prune_json_ld(
        {
            "@type": "Person",
            "@id": abs_listing + "#seller",
            "name": seller_name,
            "url": seller_url,
        }
    )

    offer = {
        "@type": "Offer",
        "priceCurrency": listing.currency,
        "price": format(listing.price_amount, ".2f"),
        "availability": "https://schema.org/InStock",
        "url": abs_listing,
        "itemCondition": "https://schema.org/UsedCondition",
        "seller": {"@id": abs_listing + "#seller"},
    }
    place_node = _property_place_json_ld(listing)
    if place_node is not None:
        offer["availableAtOrFrom"] = place_node

    desc_plain = strip_tags(listing.description or "").strip()
    desc_plain = " ".join(desc_plain.split())[:2000]

    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": listing.title,
        "description": desc_plain,
        "url": abs_listing,
        "brand": {"@type": "Brand", "name": brand},
        "offers": offer,
        "seller": seller_node,
    }

    if image_urls:
        data["image"] = image_urls[0] if len(image_urls) == 1 else image_urls

    if trust.get("verified"):
        data["seller"]["description"] = f"Vendedor verificado en {brand}."

    return json.dumps(_prune_json_ld(data), ensure_ascii=False)


def listing_list(request):
    redirect_response = browse_category_canonical_redirect(request)
    if redirect_response is not None:
        return redirect_response
    page = build_category_page(request)
    return render(request, page.template, page.render_dict())


def listing_list_legacy(request):
    """Legacy /listings/ browse: 301 redirect to /anuncios/ preserving query."""
    url = reverse("browse")
    if request.META.get("QUERY_STRING"):
        url = f"{url}?{request.META['QUERY_STRING']}"
    return redirect(url, permanent=True)


def listing_create_legacy(request):
    """Legacy /listings/create/: 301 redirect to /publicar/."""
    return redirect("publish", permanent=True)


def listing_detail_seo(request, category_slug, listing_slug):
    qs = apply_query_plan(Listing.objects.all(), LISTING_DETAIL_ORM_PLAN)
    listing = get_object_or_404(qs, slug=listing_slug)
    is_owner = _is_listing_owner(request, listing)
    if not _is_listing_public(listing) and not is_owner:
        return _render_listing_not_found(request)
    # If category doesn't match, redirect to canonical SEO URL.
    if listing.category.slug != category_slug:
        return redirect(listing, permanent=True)
    return listing_detail(request, slug=listing.slug)


def listing_detail_legacy(request, slug):
    """Legacy /listings/<slug>/ detail: 301 redirect to SEO URL."""
    listing = get_object_or_404(
        Listing.objects.select_related("category", "zone"),
        slug=slug,
    )
    if not _is_listing_public(listing) and not _is_listing_owner(request, listing):
        return _render_listing_not_found(request)
    return redirect(listing, permanent=True)


def listing_detail(request, slug):
    qs = apply_query_plan(Listing.objects.all(), LISTING_DETAIL_ORM_PLAN)
    listing = get_object_or_404(qs, slug=slug)
    is_owner = _is_listing_owner(request, listing)
    is_public = _is_listing_public(listing)
    if not is_public and not is_owner:
        return _render_listing_not_found(request)

    seller_verification = seller_verification_bundle(listing.seller)
    listing_json_ld = _build_listing_json_ld(request, listing, seller_verification)

    report_form = None
    if request.user.is_authenticated and not is_owner:
        report_form = ListingReportForm()

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    desc_src = (listing.description or listing.title or "").strip()
    words = desc_src.split()[:32]
    meta_description = " ".join(words)
    if len(meta_description) > 160:
        meta_description = meta_description[:157].rsplit(" ", 1)[0] + "…"

    detail = build_listing_detail_context(
        listing,
        seller_verification_map={},
        is_owner=is_owner,
        visible_to_public=is_public,
    )
    canonical_href_override = request.build_absolute_uri(
        reverse(
            "listing_detail_seo",
            kwargs={
                "category_slug": listing.category.slug,
                "listing_slug": listing.slug,
            },
        )
    )

    detail_context = {
        "detail": detail,
        "listing_json_ld": listing_json_ld,
        "report_form": report_form,
        "meta_title": f"{listing.title} | {brand}",
        "meta_description": meta_description
        or f"Anuncio en {brand}: precio, fotos y contacto seguro con el vendedor.",
        "canonical_href_override": canonical_href_override,
    }
    if not is_public:
        detail_context["meta_robots"] = PRIVATE_PAGE_ROBOTS
    gallery_urls = listing_gallery_absolute_urls(request, listing, limit=1)
    if gallery_urls:
        detail_context["social_share_image_url"] = gallery_urls[0]
        detail_context["social_share_image_type"] = _image_content_type_from_url(
            gallery_urls[0]
        )
        detail_context["social_share_image_alt"] = listing.title

    return render(
        request,
        "listings/listing_detail.html",
        detail_context,
    )


def listing_contact_panel(request, slug):
    """
    HTMX contact flow with trust gates:
    - seller → self partial
    - buyer/visitor → interest form
    """
    listing = get_object_or_404(
        Listing.objects.published().select_related("seller", "zone"),
        slug=slug,
    )
    seller_verification = seller_verification_bundle(listing.seller)
    contact_surface = (
        request.POST.get("surface")
        if request.method == "POST"
        else request.GET.get("surface")
    )
    is_modal_surface = contact_surface == "modal"
    contact_context = {
        "contact_surface": "modal" if is_modal_surface else "detail",
        "contact_target": (
            "#listing-contact-modal-body"
            if is_modal_surface
            else "#contact-panel-mount"
        ),
    }

    if (
        request.user.is_authenticated
        and request.user.pk == listing.seller_id
    ):
        if request.method == "GET":
            if not request.htmx:
                return redirect(listing)
            return render(
                request,
                "listings/partials/contact_self.html",
                {"listing": listing, "seller_verification": seller_verification, **contact_context},
            )
        if request.htmx:
            return render(
                request,
                "listings/partials/contact_self.html",
                {"listing": listing, "seller_verification": seller_verification, **contact_context},
            )
        messages.error(request, "No puedes enviarte un mensaje a ti mismo.")
        return redirect(listing)

    if request.method == "GET":
        if not request.htmx:
            return redirect(listing)
        initial = {}
        if request.user.is_authenticated:
            initial = {
                "buyer_name": request.user.get_full_name(),
                "buyer_email": request.user.email,
            }
        form = ListingInterestForm(initial=initial)
        return render(
            request,
            "listings/partials/contact_panel.html",
            {
                "listing": listing,
                "form": form,
                "seller_verification": seller_verification,
                **contact_context,
            },
        )

    if request.method == "POST":
        form = ListingInterestForm(request.POST)
        if form.is_valid():
            submission = InterestSubmission(
                listing=listing,
                buyer_user=request.user if request.user.is_authenticated else None,
                buyer_name=form.cleaned_data["buyer_name"],
                buyer_email=form.cleaned_data["buyer_email"],
                message=form.cleaned_data["message"],
            )
            record_listing_interest(submission)
            if request.htmx:
                return render(
                    request,
                    "listings/partials/contact_success.html",
                    {
                        "listing": listing,
                        "related_cards": _contact_success_related_cards(listing),
                        **contact_context,
                    },
                )
            messages.success(
                request,
                f'Tu mensaje sobre «{listing.title}» fue enviado al vendedor.',
            )
            return redirect(listing)

        if request.htmx:
            return render(
                request,
                "listings/partials/contact_panel.html",
                {
                    "listing": listing,
                    "form": form,
                    "seller_verification": seller_verification,
                    **contact_context,
                },
                status=400,
            )
        messages.error(request, "Revisa los errores del formulario.")
        return redirect(listing)

    return HttpResponseBadRequest("Método no permitido")


def _listing_whatsapp_href(listing):
    seller = getattr(listing, "seller", None)
    verification = getattr(seller, "verification", None) if seller is not None else None
    if not verification:
        return ""
    if not getattr(verification, "whatsapp_contact_enabled", False):
        return ""

    raw_cc = (getattr(verification, "phone_country_code", "") or "").strip()
    raw_num = (getattr(verification, "phone_number", "") or "").strip()
    cc_digits = re.sub(r"\D", "", raw_cc)
    num_digits = re.sub(r"\D", "", raw_num)
    if not num_digits:
        return ""

    digits = num_digits
    if cc_digits and not digits.startswith(cc_digits):
        digits = f"{cc_digits}{digits}"

    text = quote(DEFAULT_CONTACT_MESSAGE)
    return f"https://wa.me/{digits}?text={text}"


def listing_whatsapp_redirect(request, slug):
    listing = get_object_or_404(
        Listing.objects.published().select_related("seller", "seller__verification", "zone"),
        slug=slug,
    )
    href = _listing_whatsapp_href(listing)
    if not href:
        messages.info(
            request,
            "Este vendedor aún no tiene WhatsApp disponible. Puedes enviar el formulario.",
        )
        return redirect(listing)
    record_listing_whatsapp_lead(
        listing,
        buyer_user=request.user if request.user.is_authenticated else None,
    )
    return redirect(href)


def category_legacy_redirect(request, slug):
    return redirect("category_landing", slug=slug, permanent=True)


def category_landing(request, slug):
    redirect_response = vehicle_legacy_filter_canonical_redirect(request)
    if redirect_response is not None:
        return redirect_response
    page = build_category_page(request, category_slug=slug)
    return render(request, page.template, page.render_dict())


@login_required
@require_POST
def listing_report(request, slug):
    listing = get_object_or_404(Listing.objects.published(), slug=slug)
    if listing.seller_id == request.user.pk:
        messages.error(request, "No puedes reportar tu propio anuncio.")
        return redirect(listing)

    form = ListingReportForm(request.POST)
    if form.is_valid():
        _, created = ListingReport.objects.get_or_create(
            reporter=request.user,
            listing=listing,
            defaults={"reason": form.cleaned_data["reason"]},
        )
        if created:
            messages.success(request, "Gracias: recibimos tu reporte.")
        else:
            messages.info(request, "Ya habías reportado este anuncio.")
        sync_listing_flag(listing.pk)
    else:
        messages.error(request, "Elige un motivo válido para el reporte.")

    return redirect(listing)


def _publish_meta_description(category: Category, category_slug: str) -> str:
    desc = (category.description or "").strip()
    if desc:
        return desc[:300] + ("…" if len(desc) > 300 else "")
    if category_slug in EXTENSION_PUBLISH_META:
        return EXTENSION_PUBLISH_META[category_slug]
    return (
        f"Publica tu anuncio en {category.name}: descripción, precio, ubicación y fotos. "
        "Llega a compradores en tu ciudad."
    )


def _commit_base_listing(
    base_form,
    user,
    category,
    *,
    published_by_platform: bool = False,
) -> Listing:
    listing = base_form.save(commit=False)
    listing.seller = user
    listing.category = category
    listing.published_by_platform = published_by_platform
    listing.status = base_form.cleaned_data.get("publish_state") or Listing.Status.PUBLISHED
    if not listing.currency:
        listing.currency = "USD"
    listing.save()
    return listing


def _created_listing_redirect(listing, *, admin_dashboard: bool):
    if admin_dashboard:
        return redirect("adminapp:listing_detail", pk=listing.pk)
    return redirect(listing)


def _account_dashboard_extra_context(request, **overrides):
    """Contexto base para vistas dentro de Mi cuenta (section / título sobreescribibles)."""
    User = get_user_model()
    user = User.objects.get(pk=request.user.pk)
    verification, _ = UserVerification.objects.get_or_create(user=user)
    ctx = {
        "account_user": user,
        "verification": verification,
        "phone_verified": bool(verification.phone_verified),
        "section": "create",
        "page_obj": None,
        "account_page_title": "Crear anuncio",
    }
    ctx.update(overrides)
    return ctx


def _render_listing_edit_response(request, ctx: dict, *, account_dashboard: bool):
    """Plantilla pública de edición o panel Mi cuenta + HTMX."""
    if not account_dashboard:
        return render(request, "listings/listing_form.html", ctx)
    listing = ctx["listing"]
    merged = {
        **_account_dashboard_extra_context(
            request,
            section="edit",
            account_page_title="Editar anuncio",
        ),
        **ctx,
        "form_action_url": reverse(
            "users:account_listing_edit",
            kwargs={"slug": listing.slug},
        ),
        "cancel_url": reverse("users:account_listings"),
    }
    if getattr(request, "htmx", False):
        return render(request, "users/partials/account_main.html", merged)
    return render(request, "users/account_dashboard.html", merged)


def _render_publish_response(
    request,
    template_name,
    context,
    *,
    account_dashboard: bool,
    admin_dashboard: bool = False,
):
    if admin_dashboard:
        admin_context = {
            **context,
            "admin_section": "listings",
            "admin_page_title": context.get("heading") or "Publicar anuncio",
            "listings_clear_url": reverse("adminapp:listings"),
            "publish_admin": True,
        }
        template = (
            "adminapp/fragments/listing_publish_main.html"
            if getattr(request, "htmx", False)
            else "adminapp/listings/publish.html"
        )
        return render(request, template, admin_context)
    if not account_dashboard:
        return render(request, template_name, context)
    merged = {**_account_dashboard_extra_context(request), **context}
    merged.setdefault("section", "create")
    if getattr(request, "htmx", False):
        return render(request, "users/partials/account_main.html", merged)
    return render(request, "users/account_dashboard.html", merged)


def create_listing_base(
    request,
    account_dashboard: bool = False,
    admin_dashboard: bool = False,
):
    """Selector: todas las categorías raíz desde BD (sin hardcode en plantillas)."""
    if _is_admin_user(request.user) and not admin_dashboard:
        return _admin_panel_redirect(request)

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    heading = "Publicar anuncio"
    if admin_dashboard:
        heading = f"Publicar anuncio de {brand}"
    ctx = {
        "meta_title": f"Publicar anuncio | {brand}",
        "meta_description": (
            "Elegí una categoría y completá tu anuncio con fotos y precio. "
            "Algunas categorías incluyen campos extra para describir mejor tu producto."
        ),
        "meta_robots": PRIVATE_PAGE_ROBOTS,
        "heading": heading,
        "publish_categories": root_categories(),
        "publish_mode": "chooser",
        "use_account_urls": account_dashboard,
        "use_admin_urls": admin_dashboard,
    }
    return _render_publish_response(
        request,
        "listings/create/base.html",
        ctx,
        account_dashboard=account_dashboard,
        admin_dashboard=admin_dashboard,
    )


@login_required
def create_listing_in_category(
    request,
    category_slug,
    *,
    account_dashboard: bool = False,
    admin_dashboard: bool = False,
):
    """
    Publicar en una categoría raíz: /publicar/<slug>/.
    Slugs extendidos (OneToOne): autos, inmuebles, motos, electronica, hogar.
    Resto → formulario base.
    """
    if _is_admin_user(request.user) and not admin_dashboard:
        return _admin_panel_redirect(request)

    category = get_object_or_404(
        Category.objects.filter(parent__isnull=True),
        slug=category_slug,
    )
    kind = publish_flow_kind(category_slug)
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    if admin_dashboard:
        url_name = "adminapp:listing_publish_in_category"
        cancel_name = "adminapp:listing_publish"
    elif account_dashboard:
        url_name = "users:account_publish_in_category"
        cancel_name = "users:account_publish"
    else:
        url_name = "publish_in_category"
        cancel_name = "publish"
    meta_description = _publish_meta_description(category, category.slug)
    specific = None
    template_name = "listings/create/simple.html"
    publish_mode = "simple"
    specific_section_title = None
    specific_fields_grid = False
    base_form_kwargs = {"category_slug": category.slug}

    if kind == "vehicle":
        template_name = "listings/create/vehicle.html"
        publish_mode = "vehicle"
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            specific = VehicleListingForm(request.POST)
            if base.is_valid() and specific.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        veh = specific.save(commit=False)
                        veh.listing = listing
                        veh.save()
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)
            specific = VehicleListingForm()

    elif kind == "property":
        template_name = "listings/create/property.html"
        publish_mode = "property"
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            specific = PropertyListingForm(request.POST)
            if base.is_valid() and specific.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        prop = specific.save(commit=False)
                        prop.listing = listing
                        _sync_property_location_from_base(prop, base)
                        prop.save()
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)
            specific = PropertyListingForm()

    elif kind == "motorcycle":
        template_name = "listings/create/motorcycle.html"
        publish_mode = "motorcycle"
        specific_section_title = "Detalles del producto"
        specific_fields_grid = True
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            specific = MotorcycleListingForm(request.POST)
            if base.is_valid() and specific.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        mot = specific.save(commit=False)
                        mot.listing = listing
                        mot.save()
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)
            specific = MotorcycleListingForm()

    elif kind == "electronics":
        template_name = "listings/create/electronics.html"
        publish_mode = "electronics"
        specific_section_title = "Detalles del producto"
        specific_fields_grid = True
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            specific = ElectronicsListingForm(request.POST)
            if base.is_valid() and specific.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        elec = specific.save(commit=False)
                        elec.listing = listing
                        elec.save()
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)
            specific = ElectronicsListingForm()

    elif kind == "homegoods":
        template_name = "listings/create/homegoods.html"
        publish_mode = "homegoods"
        specific_section_title = "Detalles del producto"
        specific_fields_grid = True
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            specific = HomeGoodsListingForm(request.POST)
            if base.is_valid() and specific.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        hg = specific.save(commit=False)
                        hg.listing = listing
                        hg.save()
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)
            specific = HomeGoodsListingForm()

    else:
        if request.method == "POST":
            base = BaseListingForm(request.POST, request.FILES, **base_form_kwargs)
            if base.is_valid():
                if validate_listing_image_uploads(request, base):
                    with transaction.atomic():
                        listing = _commit_base_listing(
                            base,
                            request.user,
                            category,
                            published_by_platform=admin_dashboard,
                        )
                        attach_listing_images(
                            listing, request.FILES.getlist("images")
                        )
                    messages.success(request, "El anuncio ya está publicado.")
                    return _created_listing_redirect(
                        listing,
                        admin_dashboard=admin_dashboard,
                    )
        else:
            base = BaseListingForm(initial={"currency": "USD"}, **base_form_kwargs)

    ctx = {
        "form": base,
        "specific_form": specific,
        "include_category": False,
        "category": category,
        "heading": (
            f"Publicar en {category.name}"
            if not admin_dashboard
            else f"Publicar en {category.name} como {brand}"
        ),
        "submit_label": (
            "Publicar anuncio"
            if not admin_dashboard
            else f"Publicar como {brand}"
        ),
        "meta_title": f"Publicar en {category.name} | {brand}",
        "meta_description": meta_description,
        "meta_robots": PRIVATE_PAGE_ROBOTS,
        "publish_mode": publish_mode,
        "listing_form_layout": publish_mode,
        "specific_section_title": specific_section_title,
        "specific_fields_grid": specific_fields_grid,
        "form_action_url": reverse(
            url_name,
            kwargs={"category_slug": category.slug},
        ),
        "cancel_url": reverse(cancel_name),
        "use_account_urls": account_dashboard,
        "use_admin_urls": admin_dashboard,
    }
    return _render_publish_response(
        request,
        template_name,
        ctx,
        account_dashboard=account_dashboard,
        admin_dashboard=admin_dashboard,
    )


@login_required
def listing_create(request):
    """Selector de categoría en /publicar/."""
    return create_listing_base(request, account_dashboard=False)


@login_required
def my_listings(request):
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)

    qs = user_listings_queryset(request.user)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page") or 1)
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "listings/my_listings.html",
        {
            "page_obj": page,
            "meta_title": f"Mis anuncios | {brand}",
            "meta_description": (
                f"Gestiona tus anuncios publicados en {brand}: edita precio, fotos y visibilidad."
            ),
            "meta_robots": PRIVATE_PAGE_ROBOTS,
        },
    )


def _cleanup_extensions_if_category_changed(listing, old_slug: str, new_slug: str) -> None:
    if old_slug == new_slug:
        return
    if old_slug == VEHICLE_SLUG and new_slug != VEHICLE_SLUG:
        VehicleListing.objects.filter(listing=listing).delete()
    if old_slug == PROPERTY_SLUG and new_slug != PROPERTY_SLUG:
        PropertyListing.objects.filter(listing=listing).delete()
    if old_slug == MOTORCYCLE_SLUG and new_slug != MOTORCYCLE_SLUG:
        MotorcycleListing.objects.filter(listing=listing).delete()
    if old_slug == ELECTRONICS_SLUG and new_slug != ELECTRONICS_SLUG:
        ElectronicsListing.objects.filter(listing=listing).delete()
    if old_slug == HOMEGOODS_SLUG and new_slug != HOMEGOODS_SLUG:
        HomeGoodsListing.objects.filter(listing=listing).delete()


def _sync_property_location_from_base(prop, base_form) -> None:
    if base_form.cleaned_data.get("add_location"):
        return
    from apps.listings.location_geocoding import clear_property_geocoding

    clear_property_geocoding(prop)


@login_required
def listing_edit_legacy_redirect(request, slug):
    """Legado /listings/<slug>/edit/ → edición en Mi cuenta (URL en español)."""
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)

    get_owned_listing(request.user, slug)
    return redirect("users:account_listing_edit", slug=slug)


@login_required
def listing_edit(request, slug, *, account_dashboard: bool = False):
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)

    listing = get_owned_listing(request.user, slug)
    cat_slug = listing.category.slug
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")

    if cat_slug == VEHICLE_SLUG:
        return _listing_edit_with_specific_form(
            request,
            listing,
            brand,
            account_dashboard,
            specific_form_class=VehicleListingForm,
            get_extension=get_vehicle_extension,
        )
    if cat_slug == PROPERTY_SLUG:
        return _listing_edit_with_specific_form(
            request,
            listing,
            brand,
            account_dashboard,
            specific_form_class=PropertyListingForm,
            get_extension=get_property_extension,
        )
    if cat_slug == MOTORCYCLE_SLUG:
        return _listing_edit_with_specific_form(
            request,
            listing,
            brand,
            account_dashboard,
            specific_form_class=MotorcycleListingForm,
            get_extension=get_motorcycle_extension,
            specific_section_title="Detalles del producto",
            specific_fields_grid=True,
        )
    if cat_slug == ELECTRONICS_SLUG:
        return _listing_edit_with_specific_form(
            request,
            listing,
            brand,
            account_dashboard,
            specific_form_class=ElectronicsListingForm,
            get_extension=get_electronics_extension,
            specific_section_title="Detalles del producto",
            specific_fields_grid=True,
        )
    if cat_slug == HOMEGOODS_SLUG:
        return _listing_edit_with_specific_form(
            request,
            listing,
            brand,
            account_dashboard,
            specific_form_class=HomeGoodsListingForm,
            get_extension=get_homegoods_extension,
            specific_section_title="Detalles del producto",
            specific_fields_grid=True,
        )
    return _listing_edit_generic(request, listing, brand, account_dashboard)


def _listing_edit_with_specific_form(
    request,
    listing,
    brand: str,
    account_dashboard: bool,
    *,
    specific_form_class,
    get_extension,
    specific_section_title=None,
    specific_fields_grid=False,
):
    ext = get_extension(listing)
    base_form_kwargs = {"category_slug": listing.category.slug}
    if request.method == "POST":
        base = BaseListingForm(
            request.POST,
            request.FILES,
            instance=listing,
            **base_form_kwargs,
        )
        specific = specific_form_class(request.POST, instance=ext)
        if base.is_valid() and specific.is_valid():
            if validate_listing_image_changes(request, listing, base):
                listing.status = base.cleaned_data.get("publish_state") or listing.status
                base.save()
                obj = specific.save(commit=False)
                obj.listing = listing
                if isinstance(obj, PropertyListing):
                    _sync_property_location_from_base(obj, base)
                obj.save()
                commit_listing_image_changes(request, listing)
                messages.success(request, "Anuncio actualizado.")
                if account_dashboard:
                    return redirect("users:account_listings")
                return redirect(listing)
    else:
        base = BaseListingForm(instance=listing, **base_form_kwargs)
        specific = specific_form_class(instance=ext)
    ctx = {
        "form": base,
        "specific_form": specific,
        "include_category": False,
        "listing": listing,
        "heading": "Editar anuncio",
        "submit_label": "Guardar cambios",
        "meta_title": f"Editar: {listing.title} | {brand}",
        "meta_description": (
            "Actualiza tu anuncio: descripción, precio, ubicación y fotos para atraer más contactos."
        ),
        "meta_robots": PRIVATE_PAGE_ROBOTS,
        "publish_mode": publish_flow_kind(listing.category.slug),
        "listing_form_layout": publish_flow_kind(listing.category.slug),
        "specific_section_title": specific_section_title,
        "specific_fields_grid": specific_fields_grid,
    }
    return _render_listing_edit_response(request, ctx, account_dashboard=account_dashboard)


def _listing_edit_generic(request, listing, brand: str, account_dashboard: bool):
    if request.method == "POST":
        old_slug = listing.category.slug
        form = ListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            new_slug = form.cleaned_data["category"].slug
            if validate_listing_image_changes(request, listing, form):
                _cleanup_extensions_if_category_changed(listing, old_slug, new_slug)
                listing.status = form.cleaned_data.get("publish_state") or listing.status
                form.save()
                commit_listing_image_changes(request, listing)
                messages.success(request, "Anuncio actualizado.")
                if account_dashboard:
                    return redirect("users:account_listings")
                return redirect(listing)
    else:
        form = ListingForm(instance=listing)
    ctx = {
        "form": form,
        "specific_form": None,
        "include_category": True,
        "listing": listing,
        "heading": "Editar anuncio",
        "submit_label": "Guardar cambios",
        "meta_title": f"Editar: {listing.title} | {brand}",
        "meta_description": (
            "Actualiza tu anuncio: descripción, precio, ubicación y fotos para atraer más contactos."
        ),
        "meta_robots": PRIVATE_PAGE_ROBOTS,
        "publish_mode": publish_flow_kind(listing.category.slug),
        "listing_form_layout": publish_flow_kind(listing.category.slug),
    }
    return _render_listing_edit_response(request, ctx, account_dashboard=account_dashboard)


@login_required
def listing_delete(request, slug):
    if _is_admin_user(request.user):
        return _admin_panel_redirect(request)

    listing = get_owned_listing(request.user, slug)
    if request.method == "POST":
        title = listing.title
        listing.delete()
        messages.success(
            request,
            f'Eliminamos «{title}».',
        )
        return redirect("listings:mine")
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "listings/listing_confirm_delete.html",
        {
            "listing": listing,
            "meta_title": f"Eliminar anuncio | {brand}",
            "meta_description": "Confirma si deseas eliminar este anuncio de forma permanente.",
            "meta_robots": PRIVATE_PAGE_ROBOTS,
        },
    )


def vehicle_model_options(request):
    """
    HTMX helper: returns <option> list for VehicleListingForm.model_fk.
    GET params:
      - brand_id, brand_fk or brand: MarketBrand.pk
    """
    brand_id_raw = (
        request.GET.get("brand_id")
        or request.GET.get("brand_fk")
        or request.GET.get("brand")
        or request.GET.get("marca")
        or ""
    )
    bid = scoped_brand_id_from_request_value(brand_id_raw)

    models_qs = market_model_queryset(VEHICLE_SLUG, bid)

    # Return <option> list so htmx can swap select innerHTML.
    out = ['<option value="">Selecciona el modelo</option>']
    for m in models_qs:
        out.append(f'<option value="{m.pk}">{escape(m.name)}</option>')
    return HttpResponse("\n".join(out))


def motorcycle_model_options(request):
    """
    HTMX helper: returns <option> list for MotorcycleListingForm.model_fk.
    GET params:
      - brand_fk: MarketBrand.pk
    """
    brand_id = scoped_brand_id_from_request_value(
        request.GET.get("brand_fk") or request.GET.get("brand")
    )
    out = ['<option value="">Selecciona modelo</option>']
    for model in market_model_queryset(MOTORCYCLE_SLUG, brand_id):
        out.append(f'<option value="{model.pk}">{escape(model.name)}</option>')
    return HttpResponse("\n".join(out))


def electronics_model_options(request):
    """
    HTMX helper: returns <option> list for ElectronicsListingForm.model_fk.
    GET params:
      - brand_fk: MarketBrand.pk
      - item_type: optional electronics type for scoped models
    """
    brand_id = scoped_brand_id_from_request_value(
        request.GET.get("brand_fk") or request.GET.get("brand")
    )
    item_type = (request.GET.get("item_type") or "").strip()
    out = ['<option value="">Selecciona modelo</option>']
    for model in market_model_queryset(
        ELECTRONICS_SLUG,
        brand_id,
        item_type=item_type,
    ):
        out.append(f'<option value="{model.pk}">{escape(model.name)}</option>')
    return HttpResponse("\n".join(out))


def electronics_brand_options(request):
    """
    HTMX helper: returns <option> list for ElectronicsListingForm.brand_fk.
    GET params:
      - item_type: optional electronics type for scoped brands
    """
    item_type = (request.GET.get("item_type") or "").strip()
    out = ['<option value="">Selecciona marca</option>']
    if not item_type:
        out = ['<option value="">Primero selecciona tipo</option>']
        return HttpResponse("\n".join(out))
    for brand in market_brand_queryset(ELECTRONICS_SLUG, item_type=item_type):
        out.append(f'<option value="{brand.pk}">{escape(brand.name)}</option>')
    return HttpResponse("\n".join(out))


def homegoods_model_options(request):
    """
    HTMX helper: returns <option> list for HomeGoodsListingForm.model_fk.
    GET params:
      - brand_fk: MarketBrand.pk
      - item_type: optional home goods type for scoped models
    """
    brand_id = scoped_brand_id_from_request_value(
        request.GET.get("brand_fk") or request.GET.get("brand")
    )
    item_type = (request.GET.get("item_type") or "").strip()
    out = ['<option value="">Selecciona modelo</option>']
    for model in market_model_queryset(
        HOMEGOODS_SLUG,
        brand_id,
        item_type=item_type,
    ):
        out.append(f'<option value="{model.pk}">{escape(model.name)}</option>')
    return HttpResponse("\n".join(out))


def homegoods_brand_options(request):
    """
    HTMX helper: returns <option> list for HomeGoodsListingForm.brand_fk.
    GET params:
      - item_type: optional home goods type for scoped brands
    """
    item_type = (request.GET.get("item_type") or "").strip()
    out = ['<option value="">Selecciona marca</option>']
    if not item_type:
        out = ['<option value="">Primero selecciona tipo</option>']
        return HttpResponse("\n".join(out))
    for brand in market_brand_queryset(HOMEGOODS_SLUG, item_type=item_type):
        out.append(f'<option value="{brand.pk}">{escape(brand.name)}</option>')
    return HttpResponse("\n".join(out))


@login_required
@require_POST
def listing_promote(request, pk: int):
    """
    Activa una promoción (sin pasarela): POST JSON { "type": "featured"|"boost", "days": N }.

    Solo el vendedor del anuncio o staff. Pensado para pruebas / admin hasta integrar Stripe.
    """
    listing = get_object_or_404(Listing, pk=pk)
    if listing.seller_id != request.user.pk and not getattr(
        request.user,
        "is_staff",
        False,
    ):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    ptype = (payload.get("type") or "").strip()
    try:
        days = int(payload.get("days", 0))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "days inválido"}, status=400)

    if days < 1 or days > 365:
        return JsonResponse({"detail": "days debe estar entre 1 y 365"}, status=400)

    ext = str(payload.get("external_payment_id") or "")[:255]

    try:
        promo = create_listing_promotion(
            listing,
            request.user,
            ptype,
            days,
            external_payment_id=ext,
        )
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    return JsonResponse(
        {
            "id": promo.pk,
            "type": promo.type,
            "ends_at": promo.ends_at.isoformat(),
            "listing_id": listing.pk,
        },
        status=201,
    )
