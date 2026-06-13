"""Listing domain logic (kept out of views)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable
import warnings

from django.db.models import Max, Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from PIL import Image, UnidentifiedImageError

from apps.core.emails import send_listing_interest_email

from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .models import (
    ElectronicsListing,
    ElectronicsItemType,
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
    ListingImage,
    ListingLead,
    MarketBrand,
    MarketModel,
    MarketZone,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)
from .market_taxonomy import market_brand_queryset, market_model_queryset

# Parámetros GET del filtro de autos (MVP).
LOCATION_FILTER_GET_KEYS = ("area",)

VEHICLE_FILTER_GET_KEYS = (
    *LOCATION_FILTER_GET_KEYS,
    "brand",
    "model",
    "year_from",
    "year_to",
    "price_from",
    "price_to",
    "transmission",
)

# Parámetros GET del filtro de inmuebles (MVP). `operation` y `operacion` son alias.
PROPERTY_FILTER_GET_KEYS = (
    *LOCATION_FILTER_GET_KEYS,
    "tipo",
    "operation",
    "operacion",
    "rooms",
    "bathrooms",
    "price_from",
    "price_to",
)

MOTORCYCLE_FILTER_GET_KEYS = (
    *LOCATION_FILTER_GET_KEYS,
    "brand",
    "model",
    "year_from",
    "year_to",
    "engine_cc_from",
    "engine_cc_to",
    "mileage_from",
    "mileage_to",
    "transmission",
    "fuel_type",
    "condition",
    "price_from",
    "price_to",
)

ELECTRONICS_FILTER_GET_KEYS = (
    *LOCATION_FILTER_GET_KEYS,
    "item_type",
    "brand",
    "model",
    "condition",
    "warranty",
    "price_from",
    "price_to",
)

HOME_FILTER_GET_KEYS = (
    *LOCATION_FILTER_GET_KEYS,
    "item_type",
    "brand",
    "model",
    "condition",
    "price_from",
    "price_to",
)

# SEO: landing /motos/ sin filtros ni búsqueda (canonical siempre al hub).
MOTORCYCLE_HUB_DEFAULT_META_TITLE_CORE = (
    "Motos usadas y nuevas | Compra y venta de motos"
)

MAX_LISTING_IMAGES = 10
MAX_LISTING_IMAGE_BYTES = 5 * 1024 * 1024
MAX_LISTING_IMAGE_PIXELS = 40_000_000
ALLOWED_LISTING_IMAGE_EXTS = frozenset({"jpg", "jpeg", "png", "webp"})
ALLOWED_LISTING_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


def _listing_has_images_from_cache(listing: Listing) -> bool:
    cache = getattr(listing, "_prefetched_objects_cache", None)
    if not cache or "images" not in cache:
        return False
    imgs = cache["images"]
    return bool(imgs)


def _vehicle_extension_complete(obj: VehicleListing) -> bool:
    return bool(
        obj.year
        and obj.doors
        and (obj.transmission or "").strip()
        and obj.brand_fk_id
        and obj.model_fk_id
    )


def _property_extension_complete(obj: PropertyListing) -> bool:
    return bool(
        (obj.property_type or "").strip()
        and obj.rooms
        and obj.bathrooms
        and obj.area_m2
    )


def _motorcycle_extension_complete(obj: MotorcycleListing) -> bool:
    return bool(
        obj.brand_fk_id
        and obj.model_fk_id
        and obj.year
        and (obj.transmission or "").strip()
        and (obj.fuel_type or "").strip()
        and (obj.condition or "").strip()
    )


def _electronics_extension_complete(obj: ElectronicsListing) -> bool:
    return bool(
        obj.brand_fk_id
        and obj.model_fk_id
        and (obj.condition or "").strip()
    )


def _homegoods_extension_complete(obj: HomeGoodsListing) -> bool:
    return bool((obj.condition or "").strip())


def _extension_complete_bonus(listing: Listing) -> float:
    checks: tuple[tuple[str, Callable[..., bool]], ...] = (
        ("vehicle", _vehicle_extension_complete),
        ("property", _property_extension_complete),
        ("motorcycle", _motorcycle_extension_complete),
        ("electronics", _electronics_extension_complete),
        ("homegoods", _homegoods_extension_complete),
    )
    for attr, complete_fn in checks:
        if attr not in listing.__dict__:
            continue
        rel = listing.__dict__[attr]
        if rel is not None and complete_fn(rel):
            return 2.0
    return 0.0


def compute_listing_quality_score(listing: Listing) -> float:
    """
    Puntuación determinista para ranking; sin queries: solo campos escalares del listing,
    caché de prefetch `images` y relaciones 1:1 ya resueltas en `listing.__dict__`.
    """
    score = 0.0
    if _listing_has_images_from_cache(listing):
        score += 2.0
    desc = listing.description or ""
    if len(desc) > 120:
        score += 1.0
    if listing.price_amount is not None:
        score += 1.0
    if (listing.public_location or "").strip():
        score += 1.0
    score += _extension_complete_bonus(listing)
    return float(score)


@dataclass
class InterestSubmission:
    listing: Listing
    buyer_user: object | None
    buyer_name: str
    buyer_email: str
    message: str


def record_listing_interest(submission: InterestSubmission) -> ListingLead:
    """
    Guarda el lead antes de notificar: si el email falla, el vendedor no pierde
    el contacto en Mi cuenta.
    """
    listing = submission.listing
    lead = ListingLead.objects.create(
        listing=listing,
        seller=listing.seller,
        buyer_user=submission.buyer_user,
        source=ListingLead.Source.FORM,
        buyer_name=submission.buyer_name,
        buyer_email=submission.buyer_email,
        message=submission.message,
        email_status=ListingLead.EmailStatus.PENDING,
    )
    try:
        send_listing_interest_email(
            listing,
            submission.buyer_name,
            submission.buyer_email,
            submission.message,
        )
    except Exception as exc:
        lead.email_status = ListingLead.EmailStatus.FAILED
        lead.email_error = str(exc)[:1000]
        lead.save(update_fields=["email_status", "email_error", "updated_at"])
    else:
        lead.email_status = ListingLead.EmailStatus.SENT
        lead.save(update_fields=["email_status", "updated_at"])
    return lead


def record_listing_whatsapp_lead(listing: Listing, buyer_user=None) -> ListingLead:
    """Registra intención de contacto por WhatsApp antes de redirigir fuera del sitio."""
    buyer_name = ""
    buyer_email = ""
    if buyer_user is not None and getattr(buyer_user, "is_authenticated", False):
        buyer_name = buyer_user.get_full_name()
        buyer_email = buyer_user.email
    return ListingLead.objects.create(
        listing=listing,
        seller=listing.seller,
        buyer_user=buyer_user if getattr(buyer_user, "is_authenticated", False) else None,
        source=ListingLead.Source.WHATSAPP,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        message="Contacto iniciado por WhatsApp.",
        email_status=ListingLead.EmailStatus.NOT_APPLICABLE,
    )


def market_zone_queryset() -> QuerySet[MarketZone]:
    return MarketZone.objects.filter(is_active=True).order_by("sort_order", "name")


def _market_zone_by_slug(area_slug: str | None) -> MarketZone | None:
    slug = (area_slug or "").strip()
    if not slug:
        return None
    return MarketZone.objects.filter(slug=slug, is_active=True).first()


def parse_location_filter_params(get_params: QueryDict) -> dict:
    zone = _market_zone_by_slug(get_params.get("area"))
    return {
        "area": zone.slug if zone else None,
        "area_name": zone.name if zone else None,
        "zone_id": zone.pk if zone else None,
    }


def apply_location_filter(qs: QuerySet, parsed: dict) -> QuerySet:
    if parsed.get("zone_id"):
        return qs.filter(zone_id=parsed["zone_id"])
    return qs


def location_browse_filters_active(parsed: dict) -> bool:
    return bool(parsed and parsed.get("zone_id"))


def parse_property_list_filter_params(get_params: QueryDict) -> dict:
    """Lee GET para filtros de inmuebles; valores inválidos → None (se ignoran)."""
    tipo_raw = (get_params.get("tipo") or "").strip()
    valid_tipo = {c[0] for c in PropertyListing.PropertyType.choices}
    property_type = tipo_raw if tipo_raw in valid_tipo else None

    op_raw = (get_params.get("operation") or get_params.get("operacion") or "").strip()
    valid_op = {c[0] for c in PropertyListing.OperationType.choices}
    operation_type = op_raw if op_raw in valid_op else None

    rooms_min = _safe_int(get_params.get("rooms"), min_v=1, max_v=99)
    bathrooms_min = _safe_int(get_params.get("bathrooms"), min_v=1, max_v=99)

    price_from = _safe_price(get_params.get("price_from"))
    price_to = _safe_price(get_params.get("price_to"))
    if price_from is not None and price_to is not None and price_from > price_to:
        price_from, price_to = price_to, price_from

    return {
        **parse_location_filter_params(get_params),
        "property_type": property_type,
        "operation_type": operation_type,
        "rooms_min": rooms_min,
        "bathrooms_min": bathrooms_min,
        "price_from": price_from,
        "price_to": price_to,
    }


def apply_property_list_filters(qs: QuerySet, parsed: dict) -> QuerySet:
    """Restringe queryset según PropertyListing. Llamar solo con categoría inmuebles."""
    qs = apply_location_filter(qs, parsed)
    if parsed.get("property_type"):
        qs = qs.filter(property__property_type=parsed["property_type"])
    if parsed.get("operation_type"):
        qs = qs.filter(property__operation_type=parsed["operation_type"])
    if parsed.get("rooms_min") is not None:
        qs = qs.filter(property__rooms__gte=parsed["rooms_min"])
    if parsed.get("bathrooms_min") is not None:
        qs = qs.filter(property__bathrooms__gte=parsed["bathrooms_min"])
    if parsed.get("price_from") is not None:
        qs = qs.filter(price_amount__gte=parsed["price_from"])
    if parsed.get("price_to") is not None:
        qs = qs.filter(price_amount__lte=parsed["price_to"])
    return qs


def _market_brand_name(brand_id: int | None) -> str | None:
    if not brand_id:
        return None
    return (
        MarketBrand.objects.filter(pk=brand_id, is_active=True)
        .values_list("name", flat=True)
        .first()
    )


def _market_model_name(model_id: int | None) -> str | None:
    if not model_id:
        return None
    return (
        MarketModel.objects.filter(pk=model_id, is_active=True)
        .values_list("name", flat=True)
        .first()
    )


def market_brand_options_for_browse(
    category_slug: str,
    *,
    item_type: str | None = None,
) -> QuerySet[MarketBrand]:
    return market_brand_queryset(category_slug, item_type=item_type)


def market_model_options_for_browse(
    category_slug: str,
    brand_id: int | None,
    *,
    item_type: str | None = None,
) -> list[tuple[int, str]]:
    if not brand_id:
        return []
    return list(
        market_model_queryset(category_slug, brand_id, item_type=item_type)
        .values_list("id", "name")
    )


def parse_motorcycle_list_filter_params(get_params: QueryDict) -> dict:
    """Lee GET para filtros de motos; valores inválidos → None."""
    current_year = date.today().year
    year_max = current_year + 1

    brand_id = _safe_int(get_params.get("brand"), min_v=1)
    model_id = _safe_int(get_params.get("model"), min_v=1)
    brand = _market_brand_name(brand_id)
    model = _market_model_name(model_id)

    year_from = _safe_int(get_params.get("year_from"), min_v=1980, max_v=year_max)
    year_to = _safe_int(get_params.get("year_to"), min_v=1980, max_v=year_max)
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from

    engine_cc_from = _safe_int(get_params.get("engine_cc_from"), min_v=50, max_v=9999)
    engine_cc_to = _safe_int(get_params.get("engine_cc_to"), min_v=50, max_v=9999)
    if (
        engine_cc_from is not None
        and engine_cc_to is not None
        and engine_cc_from > engine_cc_to
    ):
        engine_cc_from, engine_cc_to = engine_cc_to, engine_cc_from

    mileage_from = _safe_int(get_params.get("mileage_from"), min_v=0, max_v=99999999)
    mileage_to = _safe_int(get_params.get("mileage_to"), min_v=0, max_v=99999999)
    if mileage_from is not None and mileage_to is not None and mileage_from > mileage_to:
        mileage_from, mileage_to = mileage_to, mileage_from

    tx_raw = (get_params.get("transmission") or "").strip()
    valid_tx = {c[0] for c in MotorcycleListing.Transmission.choices}
    transmission = tx_raw if tx_raw in valid_tx else None

    fuel_raw = (get_params.get("fuel_type") or "").strip()
    valid_fuel = {c[0] for c in MotorcycleListing.FuelType.choices}
    fuel_type = fuel_raw if fuel_raw in valid_fuel else None

    cond_raw = (get_params.get("condition") or "").strip()
    valid_cond = {c[0] for c in ItemCondition.choices}
    condition = cond_raw if cond_raw in valid_cond else None

    price_from = _safe_price(get_params.get("price_from"))
    price_to = _safe_price(get_params.get("price_to"))
    if price_from is not None and price_to is not None and price_from > price_to:
        price_from, price_to = price_to, price_from

    return {
        **parse_location_filter_params(get_params),
        "brand": brand,
        "model": model,
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": year_from,
        "year_to": year_to,
        "engine_cc_from": engine_cc_from,
        "engine_cc_to": engine_cc_to,
        "mileage_from": mileage_from,
        "mileage_to": mileage_to,
        "transmission": transmission,
        "fuel_type": fuel_type,
        "condition": condition,
        "price_from": price_from,
        "price_to": price_to,
    }


def apply_motorcycle_list_filters(qs: QuerySet, parsed: dict) -> QuerySet:
    """Restringe queryset según MotorcycleListing. Solo categoría motos."""
    qs = apply_location_filter(qs, parsed)
    if parsed.get("brand_id"):
        qs = qs.filter(motorcycle__brand_fk_id=parsed["brand_id"])
    if parsed.get("model_id"):
        mid = parsed["model_id"]
        bid = parsed.get("brand_id")
        if bid and not MarketModel.objects.filter(pk=mid, brand_id=bid).exists():
            return qs.none()
        qs = qs.filter(motorcycle__model_fk_id=mid)
    if parsed.get("year_from") is not None:
        qs = qs.filter(motorcycle__year__gte=parsed["year_from"])
    if parsed.get("year_to") is not None:
        qs = qs.filter(motorcycle__year__lte=parsed["year_to"])
    if parsed.get("engine_cc_from") is not None:
        qs = qs.filter(motorcycle__engine_cc__gte=parsed["engine_cc_from"])
    if parsed.get("engine_cc_to") is not None:
        qs = qs.filter(motorcycle__engine_cc__lte=parsed["engine_cc_to"])
    if parsed.get("mileage_from") is not None:
        qs = qs.filter(motorcycle__mileage__gte=parsed["mileage_from"])
    if parsed.get("mileage_to") is not None:
        qs = qs.filter(motorcycle__mileage__lte=parsed["mileage_to"])
    if parsed.get("transmission"):
        qs = qs.filter(motorcycle__transmission=parsed["transmission"])
    if parsed.get("fuel_type"):
        qs = qs.filter(motorcycle__fuel_type=parsed["fuel_type"])
    if parsed.get("condition"):
        qs = qs.filter(motorcycle__condition=parsed["condition"])
    if parsed.get("price_from") is not None:
        qs = qs.filter(price_amount__gte=parsed["price_from"])
    if parsed.get("price_to") is not None:
        qs = qs.filter(price_amount__lte=parsed["price_to"])
    return qs


def parse_electronics_list_filter_params(get_params: QueryDict) -> dict:
    it_raw = (get_params.get("item_type") or "").strip()
    valid_it = {c[0] for c in ElectronicsItemType.choices}
    item_type = it_raw if it_raw in valid_it else None
    brand_id = _safe_int(get_params.get("brand"), min_v=1)
    model_id = _safe_int(get_params.get("model"), min_v=1)
    brand = _market_brand_name(brand_id)
    model = _market_model_name(model_id)
    cond_raw = (get_params.get("condition") or "").strip()
    valid_cond = {c[0] for c in ItemCondition.choices}
    condition = cond_raw if cond_raw in valid_cond else None
    w_raw = get_params.get("warranty")
    warranty: bool | None = None
    if w_raw is not None and str(w_raw).strip() != "":
        s = str(w_raw).strip().lower()
        if s in ("1", "true", "yes", "y", "si", "sí", "on"):
            warranty = True
        elif s in ("0", "false", "no", "off"):
            warranty = False
    price_from = _safe_price(get_params.get("price_from"))
    price_to = _safe_price(get_params.get("price_to"))
    if price_from is not None and price_to is not None and price_from > price_to:
        price_from, price_to = price_to, price_from
    return {
        **parse_location_filter_params(get_params),
        "item_type": item_type,
        "brand": brand,
        "model": model,
        "brand_id": brand_id,
        "model_id": model_id,
        "condition": condition,
        "warranty": warranty,
        "price_from": price_from,
        "price_to": price_to,
    }


def apply_electronics_list_filters(qs: QuerySet, parsed: dict) -> QuerySet:
    qs = apply_location_filter(qs, parsed)
    if parsed.get("item_type"):
        qs = qs.filter(electronics__item_type=parsed["item_type"])
    if parsed.get("brand_id"):
        qs = qs.filter(electronics__brand_fk_id=parsed["brand_id"])
    if parsed.get("model_id"):
        mid = parsed["model_id"]
        bid = parsed.get("brand_id")
        if bid and not MarketModel.objects.filter(pk=mid, brand_id=bid).exists():
            return qs.none()
        qs = qs.filter(electronics__model_fk_id=mid)
    if parsed.get("condition"):
        qs = qs.filter(electronics__condition=parsed["condition"])
    if parsed.get("warranty") is True:
        qs = qs.filter(
            Q(electronics__warranty=True) | Q(electronics__warranty_months__gt=0)
        )
    elif parsed.get("warranty") is False:
        qs = qs.filter(electronics__warranty=False).filter(
            Q(electronics__warranty_months__isnull=True)
            | Q(electronics__warranty_months=0)
        )
    if parsed.get("price_from") is not None:
        qs = qs.filter(price_amount__gte=parsed["price_from"])
    if parsed.get("price_to") is not None:
        qs = qs.filter(price_amount__lte=parsed["price_to"])
    return qs


def electronics_browse_filters_active(parsed: dict) -> bool:
    if not parsed:
        return False
    if location_browse_filters_active(parsed):
        return True
    if parsed.get("item_type"):
        return True
    if parsed.get("brand"):
        return True
    if parsed.get("model"):
        return True
    if parsed.get("condition"):
        return True
    if parsed.get("warranty") is not None:
        return True
    if parsed.get("price_from") is not None:
        return True
    if parsed.get("price_to") is not None:
        return True
    return False


def electronics_hub_uses_default_meta_title(
    *,
    q_raw: str,
    parsed: dict,
) -> bool:
    return not bool(q_raw) and not electronics_browse_filters_active(parsed)


ELECTRONICS_HUB_DEFAULT_META_TITLE_CORE = (
    "Compra y venta de electrónicos usados y nuevos"
)


def build_electronics_hub_default_meta_description(
    *,
    city: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de electrónica en {city}. "
        "Celulares, laptops, Smart TVs, consolas, audio y accesorios. "
        "Filtrá por tipo, marca, condición, garantía y precio."
    )


def electronics_item_type_choices_tuple():
    return ElectronicsItemType.choices


def build_electronics_browse_heading(
    *,
    city: str,
    parsed: dict,
) -> str:
    item_type = parsed.get("item_type")
    item_type_label = dict(ElectronicsItemType.choices).get(item_type, "")
    parts: list[str] = [item_type_label or "Electrónica"]
    if parsed.get("brand"):
        parts.append(parsed["brand"])
    if parsed.get("condition"):
        condition_labels = {
            ItemCondition.NUEVO: "nuevos",
            ItemCondition.USADO: "usados",
            ItemCondition.REFURBISHED: "reacondicionados",
        }
        parts.append(condition_labels.get(parsed["condition"], parsed["condition"]))
    if parsed.get("warranty") is True:
        parts.append("con garantía")
    elif parsed.get("warranty") is False:
        parts.append("sin garantía")
    head = " ".join(parts) if len(parts) > 1 else "Electrónica"
    if parsed.get("price_from") or parsed.get("price_to"):
        pf = parsed.get("price_from")
        pt = parsed.get("price_to")
        if pf is not None and pt is not None:
            head = f"{head} · USD {pf} – {pt}"
        elif pf is not None:
            head = f"{head} · desde USD {pf}"
        elif pt is not None:
            head = f"{head} · hasta USD {pt}"
    return f"{head} en {_market_place_label(city, parsed)}"


def build_electronics_meta_description(
    *,
    city: str,
    heading_hint: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de electrónica en {city}. "
        f"{heading_hint}. Filtrá por tipo, marca, condición, garantía y precio."
    )


def parse_home_filters(get_params: QueryDict) -> dict:
    it_raw = (get_params.get("item_type") or "").strip()
    valid_it = {c[0] for c in HomeItemType.choices}
    item_type = it_raw if it_raw in valid_it else None
    brand_id = _safe_int(get_params.get("brand"), min_v=1)
    model_id = _safe_int(get_params.get("model"), min_v=1)
    brand = _market_brand_name(brand_id)
    model = _market_model_name(model_id)
    cond_raw = (get_params.get("condition") or "").strip()
    valid_cond = {c[0] for c in ItemCondition.choices}
    condition = cond_raw if cond_raw in valid_cond else None
    price_from = _safe_price(get_params.get("price_from"))
    price_to = _safe_price(get_params.get("price_to"))
    if price_from is not None and price_to is not None and price_from > price_to:
        price_from, price_to = price_to, price_from
    return {
        **parse_location_filter_params(get_params),
        "item_type": item_type,
        "brand": brand or None,
        "model": model or None,
        "brand_id": brand_id,
        "model_id": model_id,
        "condition": condition,
        "price_from": price_from,
        "price_to": price_to,
    }


def apply_home_filters(qs: QuerySet, parsed: dict) -> QuerySet:
    qs = apply_location_filter(qs, parsed)
    if parsed.get("item_type"):
        qs = qs.filter(homegoods__item_type=parsed["item_type"])
    if parsed.get("brand_id"):
        qs = qs.filter(homegoods__brand_fk_id=parsed["brand_id"])
    if parsed.get("model_id"):
        mid = parsed["model_id"]
        bid = parsed.get("brand_id")
        if bid and not MarketModel.objects.filter(pk=mid, brand_id=bid).exists():
            return qs.none()
        qs = qs.filter(homegoods__model_fk_id=mid)
    if parsed.get("condition"):
        qs = qs.filter(homegoods__condition=parsed["condition"])
    if parsed.get("price_from") is not None:
        qs = qs.filter(price_amount__gte=parsed["price_from"])
    if parsed.get("price_to") is not None:
        qs = qs.filter(price_amount__lte=parsed["price_to"])
    return qs


def home_browse_filters_active(parsed: dict) -> bool:
    if not parsed:
        return False
    if location_browse_filters_active(parsed):
        return True
    if parsed.get("item_type"):
        return True
    if parsed.get("brand"):
        return True
    if parsed.get("model"):
        return True
    if parsed.get("condition"):
        return True
    if parsed.get("price_from") is not None:
        return True
    if parsed.get("price_to") is not None:
        return True
    return False


def home_hub_uses_default_meta_title(
    *,
    q_raw: str,
    parsed: dict,
) -> bool:
    return not bool(q_raw) and not home_browse_filters_active(parsed)


HOME_HUB_DEFAULT_META_TITLE_CORE = (
    "Compra y venta de artículos para el hogar nuevos y usados"
)


def build_home_hub_default_meta_description(
    *,
    city: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de hogar en {city}. "
        "Muebles, electrodomésticos, cocina, decoración y más. "
        "Filtrá por tipo, marca, modelo, condición y precio."
    )


def build_home_browse_heading(
    *,
    city: str,
    parsed: dict,
) -> str:
    parts: list[str] = ["Hogar"]
    if parsed.get("item_type"):
        label = dict(HomeItemType.choices).get(
            parsed["item_type"], parsed["item_type"]
        )
        parts.append(label.lower())
    if parsed.get("brand"):
        parts.append(parsed["brand"])
    if parsed.get("model"):
        parts.append(parsed["model"])
    if parsed.get("condition"):
        label = dict(ItemCondition.choices).get(
            parsed["condition"], parsed["condition"]
        )
        parts.append(label.lower())
    head = " ".join(parts) if len(parts) > 1 else "Hogar"
    if parsed.get("price_from") or parsed.get("price_to"):
        pf = parsed.get("price_from")
        pt = parsed.get("price_to")
        if pf is not None and pt is not None:
            head = f"{head} · USD {pf} – {pt}"
        elif pf is not None:
            head = f"{head} · desde USD {pf}"
        elif pt is not None:
            head = f"{head} · hasta USD {pt}"
    return f"{head} en {_market_place_label(city, parsed)}"


def build_home_meta_description(
    *,
    city: str,
    heading_hint: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de hogar en {city}. "
        f"{heading_hint}. Filtrá por tipo de artículo, marca, modelo, "
        "condición y precio."
    )


def home_item_type_choices_tuple():
    return HomeItemType.choices


def _safe_int(
    raw,
    *,
    min_v: int | None = None,
    max_v: int | None = None,
) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if not s.isdigit():
        return None
    try:
        v = int(s)
    except (TypeError, ValueError):
        return None
    if min_v is not None and v < min_v:
        return None
    if max_v is not None and v > max_v:
        return None
    return v


def _safe_price(raw) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if not s.isdigit():
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if d < 0:
        return None
    if d > Decimal("999999999999.99"):
        return None
    return d


def parse_vehicle_list_filter_params(get_params: QueryDict) -> dict:
    """
    Lee GET para filtros de autos; valores inválidos → None (se ignoran).
    Acepta `brand`/`model` (canónico) o `marca`/`modelo` (legacy en parser).
    """
    current_year = date.today().year
    year_max = current_year + 1

    brand_id = _safe_int(
        get_params.get("brand") or get_params.get("marca"),
        min_v=1,
    )
    model_id = _safe_int(
        get_params.get("model") or get_params.get("modelo"),
        min_v=1,
    )
    brand = _market_brand_name(brand_id)
    model = _market_model_name(model_id)

    year_from = _safe_int(get_params.get("year_from"), min_v=1980, max_v=year_max)
    year_to = _safe_int(get_params.get("year_to"), min_v=1980, max_v=year_max)
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from

    price_from = _safe_price(get_params.get("price_from"))
    price_to = _safe_price(get_params.get("price_to"))
    if price_from is not None and price_to is not None and price_from > price_to:
        price_from, price_to = price_to, price_from

    tx_raw = (get_params.get("transmission") or "").strip()
    valid_tx = {c[0] for c in VehicleListing.Transmission.choices}
    transmission = tx_raw if tx_raw in valid_tx else None

    return {
        **parse_location_filter_params(get_params),
        "brand": brand,
        "model": model,
        "brand_id": brand_id,
        "model_id": model_id,
        "year_from": year_from,
        "year_to": year_to,
        "price_from": price_from,
        "price_to": price_to,
        "transmission": transmission,
    }


def apply_vehicle_list_filters(qs: QuerySet, parsed: dict) -> QuerySet:
    """
    Restringe queryset a anuncios con VehicleListing según filtros validados.
    Llamar solo cuando la categoría ya está acotada a autos.
    """
    qs = apply_location_filter(qs, parsed)
    if parsed.get("brand_id"):
        qs = qs.filter(vehicle__brand_fk_id=parsed["brand_id"])
    if parsed.get("model_id"):
        mid = parsed["model_id"]
        bid = parsed.get("brand_id")
        if bid and not MarketModel.objects.filter(pk=mid, brand_id=bid).exists():
            return qs.none()
        qs = qs.filter(vehicle__model_fk_id=mid)
    if parsed.get("year_from") is not None:
        qs = qs.filter(vehicle__year__gte=parsed["year_from"])
    if parsed.get("year_to") is not None:
        qs = qs.filter(vehicle__year__lte=parsed["year_to"])
    if parsed.get("price_from") is not None:
        qs = qs.filter(price_amount__gte=parsed["price_from"])
    if parsed.get("price_to") is not None:
        qs = qs.filter(price_amount__lte=parsed["price_to"])
    if parsed.get("transmission"):
        qs = qs.filter(vehicle__transmission=parsed["transmission"])
    return qs


def vehicle_browse_filters_active(parsed: dict) -> bool:
    """True si el listado de autos aplica al menos un filtro de vehículo."""
    if not parsed:
        return False
    return any(
        parsed.get(k)
        for k in (
            "zone_id",
            "brand_id",
            "model_id",
            "year_from",
            "year_to",
            "price_from",
            "price_to",
            "transmission",
        )
    )


def property_browse_filters_active(parsed: dict) -> bool:
    """True si el listado de inmuebles aplica al menos un filtro."""
    if not parsed:
        return False
    return any(
        parsed.get(k)
        for k in (
            "zone_id",
            "property_type",
            "operation_type",
            "rooms_min",
            "bathrooms_min",
            "price_from",
            "price_to",
        )
    )


def motorcycle_browse_filters_active(parsed: dict) -> bool:
    if not parsed:
        return False
    return any(
        parsed.get(k)
        for k in (
            "zone_id",
            "brand_id",
            "model_id",
            "year_from",
            "year_to",
            "engine_cc_from",
            "engine_cc_to",
            "mileage_from",
            "mileage_to",
            "transmission",
            "fuel_type",
            "condition",
            "price_from",
            "price_to",
        )
    )


def motorcycle_hub_uses_default_meta_title(
    *,
    q_raw: str,
    parsed: dict,
) -> bool:
    """True si el hub /motos/ debe usar el meta title SEO fijo (sin filtros ni q)."""
    return not bool(q_raw) and not motorcycle_browse_filters_active(parsed)


def build_motorcycle_hub_default_meta_description(
    *,
    city: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} motos nuevas y usadas en {city}. "
        "Filtrá por marca, modelo, año, cilindrada, combustible, kilometraje y precio."
    )


def build_category_hero(
    *,
    category_slug: str,
    category_name: str,
    place: str,
    filters_active: bool,
    filtered_heading: str | None,
) -> tuple[str, str]:
    """
    Título y subtítulo del hero de categoría (SEO / UX).
    Si hay filtros activos y un título enriquecido, se usa ese como H1 del hero.
    """
    filtered_heading = (filtered_heading or "").strip()
    if filters_active and filtered_heading:
        title = filtered_heading
    elif category_slug == VEHICLE_SLUG:
        title = f"Autos en {place}"
    elif category_slug == PROPERTY_SLUG:
        title = f"Inmuebles en {place}"
    elif category_slug == MOTORCYCLE_SLUG:
        title = "Motos usadas y nuevas en venta"
    elif category_slug == ELECTRONICS_SLUG:
        title = "Electrónica usada y nueva en venta"
    elif category_slug == HOMEGOODS_SLUG:
        title = "Artículos para el hogar nuevos y usados"
    else:
        title = f"{category_name} en {place}"

    if category_slug == VEHICLE_SLUG:
        subtitle = (
            "Filtrá por marca, modelo y precio. Contacta con confianza."
            if filters_active
            else "Compra y vende autos en Ecuador"
        )
    elif category_slug == PROPERTY_SLUG:
        subtitle = (
            "Filtrá por tipo, operación y habitaciones."
            if filters_active
            else "Compra y alquila propiedades en Ecuador"
        )
    elif category_slug == MOTORCYCLE_SLUG:
        subtitle = (
            "Filtrá por marca, modelo, combustible y precio."
            if filters_active
            else "Compra y vende motos en Ecuador con confianza."
        )
    elif category_slug == ELECTRONICS_SLUG:
        subtitle = (
            "Filtrá por tipo, marca, condición, garantía y precio."
            if filters_active
            else "Compra y venta de electrónicos usados y nuevos."
        )
    elif category_slug == HOMEGOODS_SLUG:
        subtitle = (
            "Filtrá por tipo, condición y precio."
            if filters_active
            else "Compra y venta de artículos para el hogar nuevos y usados."
        )
    else:
        subtitle = f"Explora {category_name.lower()} cerca de ti"

    return title, subtitle


def _market_place_label(city: str, parsed: dict) -> str:
    area_name = (parsed.get("area_name") or "").strip()
    if area_name:
        return f"{area_name}, {city}"
    return city


def build_autos_browse_heading(
    *,
    city: str,
    parsed: dict,
    brand_name: str | None,
    model_name: str | None,
) -> str:
    """
    Título visible / SEO base para listado de autos con filtros (extensible).
    """
    parts: list[str] = ["Autos"]
    if brand_name and model_name:
        parts.append(f"{brand_name} {model_name}")
    elif brand_name:
        parts.append(brand_name)
    if parsed.get("year_from") and parsed.get("year_to"):
        parts.append(f"{parsed['year_from']}–{parsed['year_to']}")
    elif parsed.get("year_from"):
        parts.append(f"desde {parsed['year_from']}")
    elif parsed.get("year_to"):
        parts.append(f"hasta {parsed['year_to']}")
    if parsed.get("transmission"):
        label = dict(VehicleListing.Transmission.choices).get(
            parsed["transmission"], parsed["transmission"]
        )
        parts.append(label.lower())
    head = " ".join(parts) if len(parts) > 1 else "Autos"
    if parsed.get("price_from") or parsed.get("price_to"):
        pf = parsed.get("price_from")
        pt = parsed.get("price_to")
        if pf is not None and pt is not None:
            head = f"{head} · USD {pf} – {pt}"
        elif pf is not None:
            head = f"{head} · desde USD {pf}"
        elif pt is not None:
            head = f"{head} · hasta USD {pt}"
    return f"{head} en {_market_place_label(city, parsed)}"


def build_autos_meta_description(
    *,
    city: str,
    heading_hint: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de autos en {city}. "
        f"{heading_hint}. Filtra por marca, modelo, año, precio y transmisión."
    )


def build_property_browse_heading(
    *,
    city: str,
    parsed: dict,
) -> str:
    tipo = parsed.get("property_type")
    op = parsed.get("operation_type")

    property_type_labels = {
        PropertyListing.PropertyType.CASA: "Casas",
        PropertyListing.PropertyType.DEPARTAMENTO: "Departamentos",
        PropertyListing.PropertyType.SUITE: "Suites",
        PropertyListing.PropertyType.TERRENO_LOTE: "Terrenos y lotes",
        PropertyListing.PropertyType.OFICINA_COMERCIAL: "Oficinas comerciales",
        PropertyListing.PropertyType.LOCAL_COMERCIAL: "Locales comerciales",
        PropertyListing.PropertyType.BODEGA_GALPON: "Bodegas y galpones",
        PropertyListing.PropertyType.HACIENDA_QUINTA: "Haciendas y quintas",
        PropertyListing.PropertyType.HABITACION: "Habitaciones",
    }
    base = property_type_labels.get(tipo, "Inmuebles")

    operation_suffixes = {
        PropertyListing.OperationType.VENTA: "en venta",
        PropertyListing.OperationType.ALQUILER: "en alquiler",
        PropertyListing.OperationType.ALQUILER_TEMPORAL: "en alquiler temporal",
    }
    suffix = operation_suffixes.get(op, "")

    place = _market_place_label(city, parsed)
    head = f"{base} {suffix} en {place}" if suffix else f"{base} en {place}"

    if parsed.get("price_from") or parsed.get("price_to"):
        pf = parsed.get("price_from")
        pt = parsed.get("price_to")
        if pf is not None and pt is not None:
            head = f"{head} · USD {pf} – {pt}"
        elif pf is not None:
            head = f"{head} · desde USD {pf}"
        elif pt is not None:
            head = f"{head} · hasta USD {pt}"

    if parsed.get("rooms_min") is not None:
        head = f"{head} · {parsed['rooms_min']}+ hab."

    return head


def build_property_meta_description(
    *,
    city: str,
    heading_hint: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de inmuebles en {city}. "
        f"{heading_hint}. Filtra por tipo, operación, habitaciones y precio."
    )


def build_motorcycle_browse_heading(
    *,
    city: str,
    parsed: dict,
) -> str:
    parts: list[str] = ["Motos"]
    brand, model = parsed.get("brand"), parsed.get("model")
    if brand and model:
        parts.append(f"{brand} {model}")
    elif brand:
        parts.append(brand)
    elif model:
        parts.append(model)
    if parsed.get("year_from") and parsed.get("year_to"):
        parts.append(f"{parsed['year_from']}–{parsed['year_to']}")
    elif parsed.get("year_from"):
        parts.append(f"desde {parsed['year_from']}")
    elif parsed.get("year_to"):
        parts.append(f"hasta {parsed['year_to']}")
    if parsed.get("transmission"):
        label = dict(MotorcycleListing.Transmission.choices).get(
            parsed["transmission"], parsed["transmission"]
        )
        parts.append(label.lower())
    if parsed.get("fuel_type"):
        label = dict(MotorcycleListing.FuelType.choices).get(
            parsed["fuel_type"], parsed["fuel_type"]
        )
        parts.append(label.lower())
    if parsed.get("engine_cc_from") and parsed.get("engine_cc_to"):
        parts.append(f"{parsed['engine_cc_from']}–{parsed['engine_cc_to']} cc")
    elif parsed.get("engine_cc_from"):
        parts.append(f"desde {parsed['engine_cc_from']} cc")
    elif parsed.get("engine_cc_to"):
        parts.append(f"hasta {parsed['engine_cc_to']} cc")
    if parsed.get("condition"):
        label = dict(ItemCondition.choices).get(
            parsed["condition"], parsed["condition"]
        )
        parts.append(label.lower())
    head = " ".join(parts) if len(parts) > 1 else "Motos"
    if parsed.get("price_from") or parsed.get("price_to"):
        pf = parsed.get("price_from")
        pt = parsed.get("price_to")
        if pf is not None and pt is not None:
            head = f"{head} · USD {pf} – {pt}"
        elif pf is not None:
            head = f"{head} · desde USD {pf}"
        elif pt is not None:
            head = f"{head} · hasta USD {pt}"
    return f"{head} en {_market_place_label(city, parsed)}"


def build_motorcycle_meta_description(
    *,
    city: str,
    heading_hint: str,
    result_count: int,
) -> str:
    return (
        f"{result_count} anuncios de motos en {city}. "
        f"{heading_hint}. Filtra por marca, modelo, año, cilindrada, combustible, "
        "kilometraje y precio."
    )


def user_listings_queryset(user):
    """Dashboard: all listings for a seller."""
    return (
        Listing.objects.filter(seller=user)
        .select_related("category", "zone")
        .prefetch_related("images")
        .order_by("-created_at")
    )


def get_owned_listing(user, slug):
    """Return listing or 404; only when seller matches."""
    return get_object_or_404(
        Listing.objects.select_related(
            "category",
            "zone",
            "seller",
            "vehicle",
            "property",
            "motorcycle",
            "electronics",
            "homegoods",
        ).prefetch_related("images"),
        slug=slug,
        seller=user,
    )


def get_vehicle_extension(listing) -> VehicleListing | None:
    try:
        return listing.vehicle
    except VehicleListing.DoesNotExist:
        return None


def get_property_extension(listing) -> PropertyListing | None:
    try:
        return listing.property
    except PropertyListing.DoesNotExist:
        return None


def get_motorcycle_extension(listing) -> MotorcycleListing | None:
    try:
        return listing.motorcycle
    except MotorcycleListing.DoesNotExist:
        return None


def get_electronics_extension(listing) -> ElectronicsListing | None:
    try:
        return listing.electronics
    except ElectronicsListing.DoesNotExist:
        return None


def get_homegoods_extension(listing) -> HomeGoodsListing | None:
    try:
        return listing.homegoods
    except HomeGoodsListing.DoesNotExist:
        return None


def validate_listing_image_uploads(
    request: HttpRequest,
    form,
    *,
    existing_image_count: int = 0,
) -> bool:
    """
    Valida cantidad, tamaño y contenido real de archivos en request.FILES['images'].
    Devuelve True si pasa; en caso contrario agrega errores al form y devuelve False.
    """
    files = [f for f in request.FILES.getlist("images") if f]
    if existing_image_count + len(files) > MAX_LISTING_IMAGES:
        form.add_error(
            None,
            f"Puedes subir como máximo {MAX_LISTING_IMAGES} fotos.",
        )
        return False
    for f in files:
        if f.size > MAX_LISTING_IMAGE_BYTES:
            form.add_error(
                None,
                "Cada imagen debe pesar como máximo 5 MB.",
            )
            return False
        name = (getattr(f, "name", "") or "").lower().strip()
        ext = name.rsplit(".", 1)[-1] if "." in name else ""
        if ext and ext not in ALLOWED_LISTING_IMAGE_EXTS:
            form.add_error(
                None,
                "Formato no soportado. Sube JPG, PNG o WEBP.",
            )
            return False
        current_pos = None
        try:
            current_pos = f.tell() if hasattr(f, "tell") else None
            if hasattr(f, "seek"):
                f.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                im = Image.open(f)
            with im:
                width, height = im.size
                if width * height > MAX_LISTING_IMAGE_PIXELS:
                    form.add_error(
                        None,
                        "La imagen es demasiado grande en dimensiones. Sube una foto de menor resolución.",
                    )
                    return False
                im.verify()
                if im.format not in ALLOWED_LISTING_IMAGE_FORMATS:
                    form.add_error(
                        None,
                        "Formato no soportado. Sube JPG, PNG o WEBP.",
                    )
                    return False
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
        ):
            form.add_error(
                None,
                "No pudimos leer una de las imágenes. Sube una foto válida en JPG, PNG o WEBP.",
            )
            return False
        finally:
            if hasattr(f, "seek"):
                try:
                    f.seek(current_pos or 0)
                except (OSError, ValueError):
                    pass
    return True


def parse_remove_image_ids(post_data) -> list[int]:
    """IDs de ListingImage marcados para borrar en edición (POST remove_images)."""
    ids: list[int] = []
    seen: set[int] = set()
    for raw in post_data.getlist("remove_images"):
        value = str(raw).strip()
        if not value.isdigit():
            continue
        image_id = int(value)
        if image_id in seen:
            continue
        seen.add(image_id)
        ids.append(image_id)
    return ids


NEW_IMAGE_ORDER_TOKEN = "__new__"


def parse_listing_image_order(post_data) -> list[int | None]:
    """Orden enviado por el editor: IDs existentes y placeholders de fotos nuevas."""
    order: list[int | None] = []
    seen_existing: set[int] = set()
    for raw in post_data.getlist("image_order"):
        for part in str(raw).split(","):
            token = part.strip()
            if not token:
                continue
            if token == NEW_IMAGE_ORDER_TOKEN:
                order.append(None)
                continue
            if token.startswith("existing:"):
                token = token.removeprefix("existing:")
            if not token.isdigit():
                continue
            image_id = int(token)
            if image_id in seen_existing:
                continue
            seen_existing.add(image_id)
            order.append(image_id)
    return order


def resolve_listing_image_removals(listing: Listing, remove_ids: list[int]) -> list[int]:
    """Solo IDs que pertenecen al anuncio (ignora IDs ajenos o inválidos)."""
    if not remove_ids:
        return []
    return list(
        ListingImage.objects.filter(
            listing_id=listing.pk,
            id__in=remove_ids,
        ).values_list("id", flat=True)
    )


def apply_listing_image_order(
    listing: Listing,
    image_order: list[int | None],
    new_images: list[ListingImage] | None = None,
) -> None:
    """Normaliza sort_order respetando ownership y dejando fotos no mencionadas al final."""
    if not image_order:
        return
    existing = list(
        ListingImage.objects.filter(listing_id=listing.pk).order_by("sort_order", "id")
    )
    if not existing:
        return

    by_id = {img.pk: img for img in existing}
    pending_new = list(new_images or [])
    ordered: list[ListingImage] = []
    seen: set[int] = set()

    for token in image_order:
        img = None
        if token is None:
            img = pending_new.pop(0) if pending_new else None
        else:
            img = by_id.get(token)
        if not img or img.pk in seen:
            continue
        ordered.append(img)
        seen.add(img.pk)

    for img in existing:
        if img.pk in seen:
            continue
        ordered.append(img)
        seen.add(img.pk)

    changed: list[ListingImage] = []
    for idx, img in enumerate(ordered):
        if img.sort_order == idx:
            continue
        img.sort_order = idx
        changed.append(img)
    if changed:
        ListingImage.objects.bulk_update(changed, ["sort_order"])


def remove_listing_images(listing: Listing, image_ids: list[int]) -> int:
    """Borra filas ListingImage y sus archivos en disco. Devuelve cantidad eliminada."""
    if not image_ids:
        return 0
    removed = 0
    for img in ListingImage.objects.filter(listing_id=listing.pk, id__in=image_ids):
        img.delete()
        removed += 1
    return removed


def validate_listing_image_changes(
    request: HttpRequest,
    listing: Listing,
    form,
) -> bool:
    """Valida altas/bajas de fotos en edición sin modificar archivos."""
    remove_ids = resolve_listing_image_removals(
        listing, parse_remove_image_ids(request.POST)
    )
    remaining = listing.images.count() - len(remove_ids)
    return validate_listing_image_uploads(
        request,
        form,
        existing_image_count=remaining,
    )


def commit_listing_image_changes(request: HttpRequest, listing: Listing) -> None:
    """Aplica bajas y altas de fotos tras guardar el anuncio."""
    remove_ids = resolve_listing_image_removals(
        listing, parse_remove_image_ids(request.POST)
    )
    remove_listing_images(listing, remove_ids)
    image_order = parse_listing_image_order(request.POST)
    agg = listing.images.aggregate(mx=Max("sort_order"))
    start_order = (agg["mx"] if agg["mx"] is not None else -1) + 1
    new_images = create_listing_images(
        listing,
        request.FILES.getlist("images"),
        start_order=start_order,
    )
    apply_listing_image_order(listing, image_order, new_images)


def create_listing_images(listing, files, start_order: int = 0) -> list[ListingImage]:
    """Create ListingImage rows from uploaded file list; returns created rows."""
    from .image_processing import generate_listing_image_variants

    created: list[ListingImage] = []
    for idx, f in enumerate(files):
        if not f:
            continue
        li = ListingImage.objects.create(
            listing=listing,
            image=f,
            sort_order=start_order + idx,
        )
        # Best-effort variants (never block upload).
        try:
            variants = generate_listing_image_variants(li.image)
            stem = f"li-{li.listing_id}-{li.pk}"
            li.image_thumb.save(f"{stem}-thumb.jpg", variants["thumb"].content, save=False)
            li.image_thumb_webp.save(f"{stem}-thumb.webp", variants["thumb_webp"].content, save=False)
            li.image_medium.save(f"{stem}-medium.jpg", variants["medium"].content, save=False)
            li.image_medium_webp.save(f"{stem}-medium.webp", variants["medium_webp"].content, save=False)
            li.image_large.save(f"{stem}-large.jpg", variants["large"].content, save=False)
            li.image_large_webp.save(f"{stem}-large.webp", variants["large_webp"].content, save=False)
            li.save(
                update_fields=[
                    "image_thumb",
                    "image_thumb_webp",
                    "image_medium",
                    "image_medium_webp",
                    "image_large",
                    "image_large_webp",
                ]
            )
        except Exception:
            # Keep original upload; variants remain null.
            pass
        created.append(li)
    return created


def attach_listing_images(listing, files, start_order: int = 0) -> int:
    """Create ListingImage rows from uploaded file list; returns new count."""
    return len(create_listing_images(listing, files, start_order=start_order))
