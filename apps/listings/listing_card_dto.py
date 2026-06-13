"""
DTO de cards de listado: única fuente de verdad de UI; plantillas solo leen CardContext.

Los builders acceden a extensiones ORM solo en Python; `build_card_context` enruta por slug.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils.html import escape

from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .models import Listing

LISTING_CARD_DTO_UNIFIED = "components/marketplace/cards/card_dto_unified.html"

_CARD_CSS_MODIFIER: dict[str, str] = {
    VEHICLE_SLUG: "card-listing--vehicle",
    PROPERTY_SLUG: "card-listing--property",
    MOTORCYCLE_SLUG: "card-listing--motorcycle",
    ELECTRONICS_SLUG: "card-listing--electronics",
    HOMEGOODS_SLUG: "card-listing--home",
}

_MAX_BADGES = 5
_MAX_QUALITY_BADGES = 2
_MAX_ATTRIBUTES = 5


@dataclass(frozen=True)
class CardContext:
    """Contrato de render: las plantillas de listado solo usan estos campos."""

    template: str
    css_modifier: str
    title: str
    price_display: str
    image_url: str | None
    image_url_webp: str | None
    image_url_2: str | None
    image_url_2_webp: str | None
    image_count: int
    link: str
    badges: tuple[str, ...]
    attributes: tuple[str, ...]
    location: str
    seo_text: str
    category_label: str
    category_href: str
    trust_label: str | None
    contact_whatsapp_url: str | None
    contact_url: str
    is_featured: bool
    is_featured_top: bool
    is_promoted_featured: bool
    is_promoted_boost: bool
    listing_id: int
    publisher_label: str


def _format_money(currency: str, amount: Decimal | float, *, decimals: int) -> str:
    q = Decimal(str(amount))
    fnum = float(q)
    if decimals == 0:
        s = f"{round(fnum):,}"
    else:
        s = format(fnum, f",.{decimals}f")
    if currency == "USD":
        return f"${s}"
    return f"{currency} {s}"


def _plain_seo_text(*, title: str, price_display: str, location: str) -> str:
    t = f"{title}. Precio: {price_display}."
    loc = (location or "").strip()
    if loc:
        t += f" {loc}."
    return t


def _first_image(listing: Listing) -> tuple[str | None, str]:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    imgs = cache.get("images") if cache else None
    if imgs is not None:
        img = imgs[0] if imgs else None
    else:
        img = listing.images.first()
    if not img:
        return None, ""
    # Prefer thumb variant when available for cards.
    u = getattr(img, "image_thumb", None)
    return (u.url if u else img.image.url), f"Foto del anuncio: {listing.title}"


def _first_image_webp(listing: Listing) -> str | None:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    imgs = cache.get("images") if cache else None
    img = (imgs[0] if imgs else None) if imgs is not None else listing.images.first()
    if not img:
        return None
    u = getattr(img, "image_thumb_webp", None)
    return str(u.url) if u else None


def _second_image_thumb(listing: Listing) -> str | None:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    imgs = cache.get("images") if cache else None
    if imgs is not None:
        if len(imgs) < 2:
            return None
        im = imgs[1]
    else:
        im = listing.images.all().order_by("sort_order", "id")[1:2].first()
    if not im:
        return None
    u = getattr(im, "image_thumb", None)
    if u:
        return str(u.url)
    return str(im.image.url) if getattr(im, "image", None) else None


def _second_image_thumb_webp(listing: Listing) -> str | None:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    imgs = cache.get("images") if cache else None
    if imgs is not None:
        if len(imgs) < 2:
            return None
        im = imgs[1]
    else:
        im = listing.images.all().order_by("sort_order", "id")[1:2].first()
    if not im:
        return None
    u = getattr(im, "image_thumb_webp", None)
    return str(u.url) if u else None


def _image_count(listing: Listing) -> int:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    imgs = cache.get("images") if cache else None
    if imgs is not None:
        return len(imgs)
    try:
        return int(listing.images.count())
    except Exception:
        return 0


def _contact_links(listing: Listing) -> tuple[str | None, str]:
    """
    Contact CTAs for cards:
    - whatsapp: internal redirect; phone is never rendered in card HTML
    - contact: HTMX endpoint for the secure contact panel
    """
    contact_url = reverse("listings:contact", kwargs={"slug": listing.slug})
    whatsapp_url = None
    try:
        verification = listing.seller.verification
    except ObjectDoesNotExist:
        verification = None
    if (
        verification
        and verification.whatsapp_contact_enabled
        and verification.phone_number
    ):
        whatsapp_url = reverse("listings:whatsapp", kwargs={"slug": listing.slug})
    return whatsapp_url, contact_url


def _card_is_featured(listing: Listing) -> bool:
    raw = getattr(listing, "is_featured", None)
    if raw is None:
        return False
    try:
        return int(raw) == 1
    except (TypeError, ValueError):
        return bool(raw)


def _quality_badges_for_listing(listing: Listing) -> list[str]:
    """Hasta 2 badges por calidad/precio (sin solapar con «Destacado» en pills)."""
    out: list[str] = []
    q = float(getattr(listing, "quality_score", 0) or 0)
    if q >= 4:
        out.append("Recomendado")
    if listing.price_amount is not None and q >= 3:
        if "Buen precio" not in out:
            out.append("Buen precio")
    return out[:_MAX_QUALITY_BADGES]


def _merge_badges_with_quality(
    category_badges: tuple[str, ...] | list[str],
    listing: Listing,
) -> tuple[str, ...]:
    q_badges = _quality_badges_for_listing(listing)
    merged: list[str] = []
    seen: set[str] = set()
    for b in q_badges:
        k = b.lower()
        if k == "destacado" or k in seen:
            continue
        merged.append(b)
        seen.add(k)
    for b in category_badges:
        if len(merged) >= _MAX_BADGES:
            break
        k = str(b).lower()
        if k == "destacado" or k in seen:
            continue
        merged.append(str(b))
        seen.add(k)
    return tuple(merged[:_MAX_BADGES])


def _promo_flags(listing: Listing) -> tuple[bool, bool]:
    """Flags desde annotations del QueryPlan (0 si no hay annotate)."""
    hf = int(getattr(listing, "has_active_featured", 0) or 0) == 1
    hb = int(getattr(listing, "has_active_boost", 0) or 0) == 1
    return hf, hb


def _card_is_featured_top(listing: Listing, featured_top_ids: frozenset[int]) -> bool:
    if not featured_top_ids:
        return False
    pk = getattr(listing, "pk", None)
    if pk is None:
        return False
    return int(pk) in featured_top_ids


def _trust_label_line(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    parts: list[str] = []
    if raw.get("verified"):
        parts.append("Verificado")
    rc = int(raw.get("review_count") or 0)
    if rc:
        rv = raw.get("rating_avg")
        if rv is None:
            rv = raw.get("avg_rating")
        if rv is not None:
            parts.append(f"⭐ {rv} ({rc})")
    label = raw.get("trust_label") or ""
    level = ""
    if label == "high":
        level = "Confianza alta"
    elif label == "medium":
        level = "Confianza media"
    elif label == "low":
        level = "Confianza baja"
    if level:
        parts.append(level)
    if not parts:
        return None
    return " · ".join(parts)


def _finalize(
    *,
    listing: Listing,
    template: str,
    css_modifier: str,
    title: str,
    price_display: str,
    image_url: str | None,
    link: str,
    badges: tuple[str, ...] | list[str],
    attributes: tuple[str, ...] | list[str],
    location: str,
    seo_text: str,
    category_label: str,
    category_href: str,
    trust_label: str | None,
    is_featured: bool,
    is_featured_top: bool,
) -> CardContext:
    safe_title = escape(str(title or ""))
    safe_loc = escape(str(location or "").strip())
    safe_cat = escape(str(category_label or "").strip())
    safe_seo = escape(str(seo_text or ""))
    merged_badges = _merge_badges_with_quality(
        tuple(badges) if not isinstance(badges, tuple) else badges,
        listing,
    )
    b_list = [escape(str(x)) for x in merged_badges]
    a_list = [escape(str(x)) for x in attributes[:_MAX_ATTRIBUTES]]
    tl = escape(str(trust_label)) if trust_label else None
    img = (str(image_url).strip() or None) if image_url else None
    img_webp = _first_image_webp(listing)
    lid = int(listing.pk) if getattr(listing, "pk", None) is not None else 0
    promo_f, promo_b = _promo_flags(listing)
    wa_url, contact_url = _contact_links(listing)
    img2 = _second_image_thumb(listing)
    img2_webp = _second_image_thumb_webp(listing)
    icount = _image_count(listing)
    publisher_label = escape(getattr(listing, "public_publisher_label", "") or "")
    return CardContext(
        template=template,
        css_modifier=str(css_modifier or "").strip(),
        title=safe_title,
        price_display=str(price_display or ""),
        image_url=img,
        image_url_webp=(str(img_webp).strip() or None) if img_webp else None,
        image_url_2=(str(img2).strip() or None) if img2 else None,
        image_url_2_webp=(str(img2_webp).strip() or None) if img2_webp else None,
        image_count=int(icount or 0),
        link=str(link or ""),
        badges=tuple(b_list),
        attributes=tuple(a_list),
        location=safe_loc,
        seo_text=safe_seo,
        category_label=safe_cat,
        category_href=str(category_href or ""),
        trust_label=tl,
        contact_whatsapp_url=wa_url,
        contact_url=contact_url,
        is_featured=bool(is_featured),
        is_featured_top=bool(is_featured_top),
        is_promoted_featured=promo_f,
        is_promoted_boost=promo_b,
        listing_id=lid,
        publisher_label=publisher_label,
    )


def _listing_basics(
    listing: Listing,
    *,
    trust_map: dict[int, dict[str, Any]],
    decimals: int = 2,
) -> dict[str, Any]:
    cat = listing.category
    loc = (listing.zone.name if getattr(listing, "zone_id", None) else "").strip()
    price_display = _format_money(listing.currency, listing.price_amount, decimals=decimals)
    link = listing.get_absolute_url()
    category_href = cat.get_absolute_url()
    category_label = cat.name
    img_url, _img_alt = _first_image(listing)
    trust_label = _trust_label_line(trust_map.get(listing.seller_id))
    return {
        "loc": loc,
        "price_display": price_display,
        "link": link,
        "category_href": category_href,
        "category_label": category_label,
        "img_url": img_url,
        "trust_label": trust_label,
    }


def _card_simple(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
    decimals: int = 2,
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=decimals)
    title = listing.title
    seo = _plain_seo_text(title=title, price_display=b["price_display"], location=b["loc"])
    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=b["price_display"],
        image_url=b["img_url"],
        link=b["link"],
        badges=(),
        attributes=(),
        location=b["loc"],
        seo_text=seo,
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def _vehicle_attribute_strings(listing: Listing) -> tuple[str, ...]:
    try:
        v = listing.vehicle  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return ()
    brand = v.brand_fk.name.strip()
    model = v.model_fk.name.strip()
    out: list[str] = []
    head = f"{brand} {model}".strip()
    if head:
        out.append(head)
    out.append(str(v.year))
    if v.mileage is not None:
        out.append(f"{int(v.mileage):,} km")
    tx = v.get_transmission_display()
    if tx:
        out.append(tx)
    return tuple(out)[:_MAX_ATTRIBUTES]


def _card_vehicle(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=2)
    attrs = _vehicle_attribute_strings(listing)
    title = listing.title
    seo = _plain_seo_text(title=title, price_display=b["price_display"], location=b["loc"])
    if attrs:
        seo = f"{seo} {' '.join(attrs)}."
    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=b["price_display"],
        image_url=b["img_url"],
        link=b["link"],
        badges=(),
        attributes=attrs,
        location=b["loc"],
        seo_text=seo.strip(),
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def _card_property(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=0)
    title = listing.title
    try:
        p = listing.property  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        p = None
    if p is None:
        return _card_simple(
            listing,
            template=template,
            css_modifier=css_modifier,
            trust_map=trust_map,
            featured_top_ids=featured_top_ids,
            decimals=0,
        )

    ptype = p.get_property_type_display()
    op = p.operation_type
    op_label = p.get_operation_type_display().lower() if op else ""
    headline = f"{ptype} en {op_label}" if op else ptype

    badge_labels: list[str] = []
    if op_label:
        badge_labels.append(f"En {op_label}")
    if p.property_condition == "nuevo":
        badge_labels.append("Nuevo")
    if p.furnished:
        badge_labels.append("Amoblado")

    rows = [
        str(p.rooms),
        str(p.bathrooms),
        f"{p.area_m2} m²",
    ]
    if p.parking_spaces is not None:
        rows.append(str(p.parking_spaces))

    attr_list = [headline, *rows]
    attr_list = attr_list[:_MAX_ATTRIBUTES]

    price_row = b["price_display"]
    seo_text = (
        f"{title}. Precio: {price_row}. {headline}. "
        f"{p.rooms} habitaciones, {p.bathrooms} baños, {p.area_m2} metros cuadrados."
    )
    if p.parking_spaces is not None:
        seo_text += f" {p.parking_spaces} parqueaderos."

    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=price_row,
        image_url=b["img_url"],
        link=b["link"],
        badges=tuple(badge_labels),
        attributes=tuple(attr_list),
        location=b["loc"],
        seo_text=seo_text,
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def _card_motorcycle(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=0)
    title = listing.title
    try:
        m = listing.motorcycle  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return _card_simple(
            listing,
            template=template,
            css_modifier=css_modifier,
            trust_map=trust_map,
            featured_top_ids=featured_top_ids,
            decimals=0,
        )

    brand = m.brand_fk.name.strip()
    model = m.model_fk.name.strip()
    headline = f"{brand} {model} · {m.year}"
    tx = m.get_transmission_display()
    fuel = m.get_fuel_type_display()
    cond = m.get_condition_display()
    cc_line = f"{m.engine_cc} cc" if m.engine_cc is not None else ""
    mileage_line = f"{int(m.mileage):,} km" if m.mileage is not None else ""

    attr_candidates = [headline]
    if cc_line:
        attr_candidates.append(cc_line)
    if mileage_line:
        attr_candidates.append(mileage_line)
    attr_candidates.extend([tx, fuel, cond])
    attributes = tuple(attr_candidates)[:_MAX_ATTRIBUTES]

    seo_plain = (
        f"{title}. Precio: {b['price_display']}. {headline}. {tx}, {fuel}, {cond}."
    )
    if cc_line:
        seo_plain += f" {cc_line}."
    if mileage_line:
        seo_plain += f" {mileage_line}."
    if b["loc"]:
        seo_plain += f" {b['loc']}."

    loc_short = b["loc"][:48] if b["loc"] else ""

    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=b["price_display"],
        image_url=b["img_url"],
        link=b["link"],
        badges=(),
        attributes=attributes,
        location=loc_short,
        seo_text=seo_plain.strip(),
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def _card_electronics(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=0)
    title = listing.title
    try:
        e = listing.electronics  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return _card_simple(
            listing,
            template=template,
            css_modifier=css_modifier,
            trust_map=trust_map,
            featured_top_ids=featured_top_ids,
            decimals=0,
        )

    type_label = e.get_item_type_display() if e.item_type else ""
    brand = e.brand_fk.name.strip()
    model = e.model_fk.name.strip()
    headline = f"{brand} {model}".strip()
    cond_label = e.get_condition_display()
    badge_labels: list[str] = []
    if type_label:
        badge_labels.append(type_label)
    if e.condition == "nuevo":
        badge_labels.append("Nuevo")
    elif e.condition == "refurbished":
        badge_labels.append("Reacondicionado")
    else:
        badge_labels.append("Usado")
    warranty_line = ""
    if e.warranty_months and e.warranty_months > 0:
        badge_labels.append(f"Garantía {e.warranty_months} m")
        warranty_line = f"Garantía {e.warranty_months} meses"
    elif e.warranty:
        badge_labels.append("Garantía")
        warranty_line = "Con garantía"

    attr_candidates = []
    if type_label:
        attr_candidates.append(type_label)
    attr_candidates.extend([headline, cond_label])
    if warranty_line:
        attr_candidates.append(warranty_line)
    attributes = tuple(attr_candidates)[:_MAX_ATTRIBUTES]

    seo_plain = f"{title}. Precio: {b['price_display']}."
    if type_label:
        seo_plain += f" {type_label}."
    seo_plain += f" {headline}. {cond_label}."
    if warranty_line:
        seo_plain += f" {warranty_line}."
    if b["loc"]:
        seo_plain += f" {b['loc']}."

    loc_short = b["loc"][:48] if b["loc"] else ""

    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=b["price_display"],
        image_url=b["img_url"],
        link=b["link"],
        badges=tuple(badge_labels),
        attributes=attributes,
        location=loc_short,
        seo_text=seo_plain.strip(),
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def _card_home(
    listing: Listing,
    *,
    template: str,
    css_modifier: str,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int],
) -> CardContext:
    b = _listing_basics(listing, trust_map=trust_map, decimals=0)
    title = listing.title
    try:
        h = listing.homegoods  # type: ignore[attr-defined]
    except ObjectDoesNotExist:
        return _card_simple(
            listing,
            template=template,
            css_modifier=css_modifier,
            trust_map=trust_map,
            featured_top_ids=featured_top_ids,
            decimals=0,
        )

    badge_labels: list[str] = []
    if h.item_type:
        badge_labels.append(h.get_item_type_display())
    if h.condition == "nuevo":
        badge_labels.append("Nuevo")
    elif h.condition == "refurbished":
        badge_labels.append("Reacondicionado")
    else:
        badge_labels.append("Usado")

    brand_line = h.brand_fk.name.strip() if h.brand_fk_id else ""
    model_line = h.model_fk.name.strip() if h.model_fk_id else ""
    headline_parts: list[str] = []
    if brand_line:
        headline_parts.append(brand_line)
    if model_line:
        headline_parts.append(model_line)
    if h.item_type:
        headline_parts.append(h.get_item_type_display())
    headline = " · ".join(headline_parts)
    material_line = (h.material or "").strip()

    attr_candidates: list[str] = []
    if headline:
        attr_candidates.append(headline)
    if material_line:
        attr_candidates.append(material_line)
    attributes = tuple(attr_candidates)[:_MAX_ATTRIBUTES]

    seo_plain = f"{title}. Precio: {b['price_display']}. {headline or title}."
    if material_line:
        seo_plain += f" {material_line}."
    if b["loc"]:
        seo_plain += f" {b['loc']}."

    loc_short = b["loc"][:48] if b["loc"] else ""

    return _finalize(
        listing=listing,
        template=template,
        css_modifier=css_modifier,
        title=title,
        price_display=b["price_display"],
        image_url=b["img_url"],
        link=b["link"],
        badges=tuple(badge_labels),
        attributes=attributes,
        location=loc_short,
        seo_text=seo_plain.strip(),
        category_label=b["category_label"],
        category_href=b["category_href"],
        trust_label=b["trust_label"],
        is_featured=_card_is_featured(listing),
        is_featured_top=_card_is_featured_top(listing, featured_top_ids),
    )


def build_card_context(
    listing: Listing,
    category_slug: str,
    *,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int] | None = None,
) -> CardContext:
    """
    Punto de entrada único: enruta por slug de categoría al DTO correcto (plugin).
    """
    from .category_engine import get_category_contract

    ft = featured_top_ids or frozenset()
    spec = get_category_contract(category_slug)
    template = (spec.card_template if spec else None) or LISTING_CARD_DTO_UNIFIED
    css_modifier = _CARD_CSS_MODIFIER.get(category_slug, "")

    dispatch: dict[str, Any] = {
        VEHICLE_SLUG: _card_vehicle,
        PROPERTY_SLUG: _card_property,
        MOTORCYCLE_SLUG: _card_motorcycle,
        ELECTRONICS_SLUG: _card_electronics,
        HOMEGOODS_SLUG: _card_home,
    }
    fn = dispatch.get(category_slug, _card_simple)
    return fn(
        listing,
        template=template,
        css_modifier=css_modifier,
        trust_map=trust_map,
        featured_top_ids=ft,
    )


def build_listing_cards_for_page(
    page_obj: Any,
    *,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int] | None = None,
) -> list[CardContext]:
    return build_listing_cards_for_listings(
        page_obj.object_list,
        trust_map=trust_map,
        featured_top_ids=featured_top_ids,
    )


def build_listing_cards_for_listings(
    rows: Iterable[Listing],
    *,
    trust_map: dict[int, dict[str, Any]],
    featured_top_ids: frozenset[int] | None = None,
) -> list[CardContext]:
    ft = featured_top_ids or frozenset()
    out: list[CardContext] = []
    for listing in rows:
        slug = listing.category.slug
        out.append(
            build_card_context(listing, slug, trust_map=trust_map, featured_top_ids=ft),
        )
    return out
