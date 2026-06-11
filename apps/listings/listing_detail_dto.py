"""
DTO de página de detalle de anuncio: la plantilla solo consume ListingDetailContext.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils.html import escape

from apps.core.seo_copy import CATEGORY_EXPLORE_LABELS
from apps.trust.services import bulk_seller_trust

from .category_engine_queryplan import (
    LISTING_LIST_BASE_PLAN,
    QueryPlan,
    apply_query_plan,
    hub_electronics_query_plan,
    hub_home_query_plan,
    hub_motorcycle_query_plan,
    hub_property_query_plan,
    hub_vehicle_query_plan,
    merge_query_plans,
)
from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .listing_card_dto import (
    _card_is_featured,
    _promo_flags,
    _quality_badges_for_listing,
    build_card_context,
)
from .models import Listing

if TYPE_CHECKING:
    from .listing_card_dto import CardContext


@dataclass(frozen=True)
class ListingDetailCta:
    """CTA declarado en DTO (sin lógica en plantilla)."""

    label: str
    htmx_url: str
    scroll_href: str


@dataclass(frozen=True)
class ListingDetailContext:
    """Contrato de render del detalle (sin acceso ORM en plantilla)."""

    # Core
    title: str
    price_display: str
    currency: str
    location: str
    category_label: str
    category_href: str
    category_explore_label: str
    listing_slug: str

    # Media (gallery_* canónico; image_* alias compat)
    gallery_images: tuple[str, ...]
    gallery_images_webp: tuple[str, ...]
    gallery_count: int
    gallery_has_multiple: bool
    gallery_show_placeholder: bool
    thumbnail_images: tuple[str, ...]
    thumbnail_images_webp: tuple[str, ...]
    gallery_image_alt: str
    image_urls: tuple[str, ...]
    primary_image: str
    total_images: int
    # Mosaico tipo marketplace (hero 50% + grilla 2×2 a la derecha); solo derivado de gallery_images.
    gallery_mosaic: bool
    gallery_mosaic_hero: str
    gallery_mosaic_hero_webp: str
    gallery_mosaic_cells: tuple[str | None, str | None, str | None, str | None]
    gallery_mosaic_cells_webp: tuple[str | None, str | None, str | None, str | None]
    gallery_strip_extra: bool
    gallery_images_json: str

    # CTAs
    primary_cta: ListingDetailCta
    secondary_cta: ListingDetailCta | None
    contact_url: str
    phone_url: str | None
    report_url: str
    contact_trust_microcopy: str
    seller_safety_microcopy: str

    # UX
    quick_attributes: tuple[str, ...]
    attributes: tuple[str, ...]
    badges: tuple[str, ...]

    # Content
    description: str
    description_short: str
    show_description_expand: bool
    safety_notice: str

    # Seller
    seller_name: str
    seller_trust_summary: str
    seller_rating: float | None
    seller_reviews_count: int
    seller_joined: str
    is_verified: bool
    seller_profile_href: str

    # Flags + owner
    is_owner: bool
    visible_to_public: bool
    owner_edit_href: str
    owner_delete_href: str
    is_featured: bool
    is_promoted_boost: bool
    is_flagged: bool

    # SEO
    seo_text: str

    # Related
    similar_listings: tuple["CardContext", ...]
    show_similar: bool


def _category_explore_label(slug: str, name: str) -> str:
    return CATEGORY_EXPLORE_LABELS.get(slug, f"Ver más anuncios de {name}")


def _hub_plan_for_category_slug(slug: str) -> QueryPlan:
    dispatch = {
        VEHICLE_SLUG: hub_vehicle_query_plan,
        PROPERTY_SLUG: hub_property_query_plan,
        MOTORCYCLE_SLUG: hub_motorcycle_query_plan,
        ELECTRONICS_SLUG: hub_electronics_query_plan,
        HOMEGOODS_SLUG: hub_home_query_plan,
    }
    fn = dispatch.get(slug, lambda _r, _c: QueryPlan())
    return merge_query_plans(LISTING_LIST_BASE_PLAN, fn(None, {}))


def _prefetched_images_ordered(listing: Listing) -> list[Any]:
    """Imágenes desde prefetch (sin query extra), ordenadas como en el modelo."""
    cache = getattr(listing, "_prefetched_objects_cache", None)
    if not cache or "images" not in cache:
        return []
    rows = list(cache["images"])
    rows.sort(
        key=lambda im: (
            int(getattr(im, "sort_order", 0) or 0),
            int(getattr(im, "pk", 0) or 0),
        ),
    )
    return rows


def _mosaic_four_cells(urls: tuple[str, ...]) -> tuple[str | None, str | None, str | None, str | None]:
    """Hasta 4 URLs tras la principal; None rellena celdas vacías (menos de 5 fotos)."""
    if len(urls) < 2:
        return (None, None, None, None)
    rest = list(urls[1:5])
    while len(rest) < 4:
        rest.append(None)
    return (rest[0], rest[1], rest[2], rest[3])


def ordered_listing_image_urls(listing: Listing, *, variant: str = "original") -> tuple[str, ...]:
    """
    URLs de galería ordenadas por sort_order.

    variant:
    - original: ListingImage.image
    - thumb   : ListingImage.image_thumb (fallback a original)
    - medium  : ListingImage.image_medium (fallback a original)
    - large   : ListingImage.image_large (fallback a original)
    """
    rows = _prefetched_images_ordered(listing)
    out: list[str] = []
    for img in rows:
        if not getattr(img, "image", None):
            continue
        if variant == "thumb" and getattr(img, "image_thumb", None):
            out.append(str(img.image_thumb.url))
        elif variant == "thumb_webp" and getattr(img, "image_thumb_webp", None):
            out.append(str(img.image_thumb_webp.url))
        elif variant == "medium" and getattr(img, "image_medium", None):
            out.append(str(img.image_medium.url))
        elif variant == "medium_webp" and getattr(img, "image_medium_webp", None):
            out.append(str(img.image_medium_webp.url))
        elif variant == "large" and getattr(img, "image_large", None):
            out.append(str(img.image_large.url))
        elif variant == "large_webp" and getattr(img, "image_large_webp", None):
            out.append(str(img.image_large_webp.url))
        else:
            out.append(str(img.image.url))
    return tuple(out)


def listing_gallery_absolute_urls(request, listing: Listing, *, limit: int = 10) -> list[str]:
    """Máximo `limit` URLs absolutas para schema.org (misma orden que el DTO)."""
    rel = ordered_listing_image_urls(listing, variant="original")[:limit]
    return [request.build_absolute_uri(u) for u in rel]


def _description_short(text: str, *, limit: int = 200) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t)
    if len(t) <= limit:
        return t
    cut = t[: limit - 1].rsplit(" ", 1)[0]
    return (cut or t[:limit]) + "…"


def _detail_chip_attributes(listing: Listing, slug: str) -> tuple[str, ...]:
    """Chips para fila rápida (misma semántica que cards, extendida)."""
    if slug == PROPERTY_SLUG:
        try:
            p = listing.property  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return ()
        chips = [
            f"🛏 {p.rooms} hab",
            f"🛁 {p.bathrooms} baños",
            f"📐 {p.area_m2} m²",
        ]
        if p.parking_spaces is not None:
            chips.append(f"🚗 {p.parking_spaces} parqueo")
        return tuple(escape(x) for x in chips)
    if slug == VEHICLE_SLUG:
        try:
            v = listing.vehicle  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return ()
        brand = v.brand_fk.name.strip()
        model = v.model_fk.name.strip()
        head = escape(f"🚗 {brand} {model}".strip())
        out = [head, escape(f"📅 {v.year}")]
        if v.mileage is not None:
            out.append(escape(f"📏 {int(v.mileage):,} km"))
        return tuple(out)
    if slug == MOTORCYCLE_SLUG:
        try:
            m = listing.motorcycle  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return ()
        brand = m.brand_fk.name.strip()
        model = m.model_fk.name.strip()
        out = [
            escape(f"🏍 {brand} {model}".strip()),
            escape(f"📅 {m.year}"),
        ]
        if m.engine_cc is not None:
            out.append(escape(f"⚙️ {m.engine_cc} cc"))
        if m.mileage is not None:
            out.append(escape(f"📏 {int(m.mileage):,} km"))
        return tuple(out)
    if slug == ELECTRONICS_SLUG:
        try:
            e = listing.electronics  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return ()
        parts: list[str] = []
        if e.item_type:
            parts.append(escape(f"📱 {e.get_item_type_display()}"))
        brand = e.brand_fk.name.strip()
        model = e.model_fk.name.strip()
        parts.extend(
            [
                escape(f"💻 {brand} {model}".strip()),
                escape(str(e.get_condition_display())),
            ]
        )
        return tuple(parts)
    if slug == HOMEGOODS_SLUG:
        try:
            h = listing.homegoods  # type: ignore[attr-defined]
        except ObjectDoesNotExist:
            return ()
        parts: list[str] = []
        if h.item_type:
            parts.append(escape(f"🏠 {h.get_item_type_display()}"))
        brand = h.brand_fk.name.strip() if h.brand_fk_id else ""
        model = h.model_fk.name.strip() if h.model_fk_id else ""
        if brand:
            parts.append(escape(f"🏷 {brand}"))
        if model:
            parts.append(escape(f"Modelo: {model}"))
        parts.append(escape(str(h.get_condition_display())))
        return tuple(parts)[:6]
    return ()


def _extended_attributes(card_attrs: tuple[str, ...], chips: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for x in card_attrs:
        k = x.strip().lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    for x in chips:
        k = x.strip().lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return tuple(out[:8])


def _detail_badges(listing: Listing, trust: dict[str, Any] | None) -> tuple[str, ...]:
    promo_f, promo_b = _promo_flags(listing)
    featured = bool(_card_is_featured(listing)) or promo_f
    quality = _quality_badges_for_listing(listing)
    verified = bool(trust and trust.get("verified"))
    ordered: list[str] = []
    if featured:
        ordered.append("Destacado")
    if promo_b:
        ordered.append("Impulsado")
    for q in quality:
        if q not in ordered:
            ordered.append(q)
    if verified and "Verificado" not in ordered:
        ordered.append("Verificado")
    return tuple(escape(str(x)) for x in ordered[:3])


def _seller_trust_summary(trust: dict[str, Any] | None) -> str:
    if not trust:
        return ""
    label = trust.get("trust_label") or ""
    if label == "high":
        return "Confianza alta"
    if label == "medium":
        return "Confianza media"
    if label == "low":
        return "Confianza baja"
    return ""


def _similar_listings_rows(listing: Listing) -> list[Listing]:
    slug = listing.category.slug
    plan = _hub_plan_for_category_slug(slug)
    qs = (
        Listing.objects.published()
        .filter(category_id=listing.category_id)
        .exclude(pk=listing.pk)
    )
    qs = apply_query_plan(qs, plan)
    return list(qs.order_by("-created_at")[:12])


def build_listing_detail_context(
    listing: Listing,
    *,
    trust_map: dict[int, dict[str, Any]],
    is_owner: bool = False,
    visible_to_public: bool = True,
) -> ListingDetailContext:
    cat = listing.category
    slug = cat.slug
    seller = listing.seller
    tm: dict[int, dict[str, Any]] = dict(trust_map)
    similar_rows = _similar_listings_rows(listing)
    need_ids = {seller.pk} | {row.seller_id for row in similar_rows}
    missing = [sid for sid in need_ids if sid not in tm]
    if missing:
        tm.update(bulk_seller_trust(missing))

    seller_trust = tm.get(seller.pk) or {}
    card = build_card_context(
        listing,
        slug,
        trust_map=tm,
        featured_top_ids=frozenset(),
    )
    chips = _detail_chip_attributes(listing, slug)
    quick_attributes = chips
    attributes = _extended_attributes(card.attributes, chips)
    badges = _detail_badges(listing, seller_trust)

    urls = ordered_listing_image_urls(listing, variant="medium")
    urls_webp = ordered_listing_image_urls(listing, variant="medium_webp")
    urls_thumb = ordered_listing_image_urls(listing, variant="thumb")
    urls_thumb_webp = ordered_listing_image_urls(listing, variant="thumb_webp")
    urls_large = ordered_listing_image_urls(listing, variant="large")
    gallery_count = len(urls)
    gallery_has_multiple = gallery_count > 1
    gallery_show_placeholder = gallery_count == 0
    thumbnail_images = urls_thumb or urls
    thumbnail_images_webp = urls_thumb_webp or urls_webp
    primary = urls[0] if urls else ""
    gallery_image_alt = str(card.title or "") if card.title else ""
    gallery_mosaic = not gallery_show_placeholder and gallery_count >= 2
    gallery_mosaic_hero = str(urls[0]) if gallery_mosaic else ""
    gallery_mosaic_hero_webp = str(urls_webp[0]) if (gallery_mosaic and urls_webp) else ""
    gallery_mosaic_cells = _mosaic_four_cells(urls) if gallery_mosaic else (None, None, None, None)
    gallery_mosaic_cells_webp = _mosaic_four_cells(urls_webp) if gallery_mosaic else (None, None, None, None)
    gallery_strip_extra = not gallery_show_placeholder and gallery_count > 5
    gallery_images_json = json.dumps(list(urls_large or urls), ensure_ascii=False)

    desc_raw = (listing.description or "").strip()
    desc_short = _description_short(desc_raw)

    rv = seller_trust.get("avg_rating")
    if rv is None:
        rv = seller_trust.get("rating_avg")
    rating_f = float(rv) if rv is not None else None
    reviews = int(seller_trust.get("review_count") or 0)

    promo_f, promo_b = _promo_flags(listing)
    is_featured = bool(_card_is_featured(listing)) or promo_f

    loc = (listing.location or "").strip()

    similar_cards = tuple(
        build_card_context(
            row,
            row.category.slug,
            trust_map=tm,
            featured_top_ids=frozenset(),
        )
        for row in similar_rows
    )

    listing_slug = str(listing.slug)
    contact_path = str(reverse("listings:contact", kwargs={"slug": listing_slug}))
    primary_cta = ListingDetailCta(
        label="Contactar vendedor",
        htmx_url=contact_path,
        scroll_href="#listing-contact",
    )
    secondary_cta: ListingDetailCta | None = None

    desc_short_esc = escape(desc_short) if desc_short else ""
    show_expand = bool(desc_raw and len(desc_raw) > 200)

    owner_edit = ""
    owner_delete = ""
    if is_owner:
        owner_edit = str(reverse("users:account_listing_edit", kwargs={"slug": listing_slug}))
        owner_delete = str(reverse("listings:delete", kwargs={"slug": listing_slug}))

    trust_summary = escape(_seller_trust_summary(seller_trust))
    try:
        verification = seller.verification
    except ObjectDoesNotExist:
        verification = None
    show_seller_name = bool(getattr(verification, "show_name_in_listings", True))
    seller_name = seller.public_name if show_seller_name else "Vendedor"
    seller_profile_links_enabled = getattr(
        settings,
        "USER_PUBLIC_PROFILE_LINKS_ENABLED",
        False,
    )
    seller_profile_href = (
        str(seller.get_absolute_url())
        if show_seller_name and seller_profile_links_enabled
        else ""
    )

    return ListingDetailContext(
        title=card.title or "",
        price_display=str(card.price_display or ""),
        currency=str(listing.currency or "USD"),
        location=escape(loc),
        category_label=str(card.category_label or ""),
        category_href=str(card.category_href or ""),
        category_explore_label=escape(_category_explore_label(cat.slug, str(cat.name or ""))),
        listing_slug=listing_slug,
        gallery_images=urls,
        gallery_images_webp=urls_webp,
        gallery_count=gallery_count,
        gallery_has_multiple=gallery_has_multiple,
        gallery_show_placeholder=gallery_show_placeholder,
        thumbnail_images=thumbnail_images,
        thumbnail_images_webp=thumbnail_images_webp,
        gallery_image_alt=gallery_image_alt,
        image_urls=urls,
        primary_image=primary,
        total_images=gallery_count,
        gallery_mosaic=gallery_mosaic,
        gallery_mosaic_hero=gallery_mosaic_hero,
        gallery_mosaic_hero_webp=gallery_mosaic_hero_webp,
        gallery_mosaic_cells=gallery_mosaic_cells,
        gallery_mosaic_cells_webp=gallery_mosaic_cells_webp,
        gallery_strip_extra=gallery_strip_extra,
        gallery_images_json=gallery_images_json,
        primary_cta=primary_cta,
        secondary_cta=secondary_cta,
        contact_url=contact_path,
        phone_url=None,
        report_url=str(reverse("listings:report", kwargs={"slug": listing_slug})),
        contact_trust_microcopy="Revisa confianza y envía un mensaje seguro.",
        seller_safety_microcopy="Nunca envíes dinero por adelantado sin verificar al vendedor.",
        quick_attributes=tuple(quick_attributes),
        attributes=tuple(attributes),
        badges=tuple(badges),
        description=desc_raw,
        description_short=desc_short_esc,
        show_description_expand=show_expand,
        safety_notice=(
            "Nunca envíes dinero por adelantado ni compartas datos bancarios sin ver al vendedor "
            "y verificar el bien. Preferí encuentros en lugares públicos y seguros."
        ),
        seller_name=escape(str(seller_name)),
        seller_trust_summary=trust_summary,
        seller_rating=rating_f,
        seller_reviews_count=reviews,
        seller_joined=escape(str(seller_trust.get("member_since_display") or "")),
        is_verified=bool(seller_trust.get("verified")),
        seller_profile_href=seller_profile_href,
        is_owner=is_owner,
        visible_to_public=visible_to_public,
        owner_edit_href=owner_edit,
        owner_delete_href=owner_delete,
        is_featured=is_featured,
        is_promoted_boost=promo_b,
        is_flagged=bool(getattr(listing, "is_flagged", False)),
        seo_text=str(card.seo_text or ""),
        similar_listings=similar_cards,
        show_similar=len(similar_cards) > 0,
    )
