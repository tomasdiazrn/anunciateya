"""
Orquestación de listados por categoría: pipeline único, SEO, cards y registro canónico.

Entrypoint público para páginas de browse / hub / ciudad / ciudad+categoría: `build_category_page`.
Las vistas deben limitarse a `render(..., page.render_dict())`; evitar duplicar filtros, SEO o armado
de querysets fuera de este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.core.exceptions import ImproperlyConfigured

from apps.categories.models import Category
from apps.categories.services import root_categories
from apps.trust.services import bulk_seller_trust

from . import services as listing_services
from .category_contract import CategoryContractSpec
from .category_engine_queryplan import (
    LISTING_LIST_BASE_PLAN,
    apply_query_plan,
    browse_listings_query_plan,
    get_cached_query_plan,
    hub_electronics_query_plan,
    hub_home_query_plan,
    hub_motorcycle_query_plan,
    hub_property_query_plan,
    hub_vehicle_query_plan,
    merge_query_plans,
)
from .category_engine_seo import (
    CategorySeoBundle,
    seo_browse_generic,
    seo_electronics,
    seo_home,
    seo_location_market,
    seo_motorcycle,
    seo_property,
    seo_simple_category,
    seo_vehicle,
)
from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .listing_card_dto import LISTING_CARD_DTO_UNIFIED
from .listing_sort import (
    apply_listing_order,
    build_sort_template_extras,
    parse_sort_param,
)
from .models import Listing, MotorcycleListing, VehicleListing

# Slug de URL → búsqueda en el campo location (icontains). Fuente única para engine y compat.
LOCATION_LANDING_CONFIG: dict[str, dict[str, Any]] = {
    "guayaquil": {
        "display": "Guayaquil",
        "needles": ["Guayaquil"],
    },
    "samborondon": {
        "display": "Samborondón",
        "needles": ["Samborondón", "Samborondon"],
    },
}

LISTING_CARD_BASE = "components/marketplace/listing_card_base.html"
BROWSE_TEMPLATE_LIST = "listings/listing_list.html"
BROWSE_TEMPLATE_CATEGORY = "listings/category_detail.html"

CATEGORY_HERO_CTA_LABELS = {
    VEHICLE_SLUG: "Publicar auto",
    PROPERTY_SLUG: "Publicar inmueble",
    MOTORCYCLE_SLUG: "Publicar moto",
    ELECTRONICS_SLUG: "Publicar electrónico",
    HOMEGOODS_SLUG: "Publicar artículo de hogar",
}
# Todas las verticales usan el mismo renderer DTO; el aspecto por categoría va en `card.css_modifier`.
LISTING_CARD_SIMPLE = LISTING_CARD_DTO_UNIFIED

BROWSE_FRAME_SEO_BUILDER: Callable[
    [HttpRequest, QuerySet, dict[str, Any]],
    CategorySeoBundle,
] = seo_browse_generic

SeoBuilder = Callable[[HttpRequest, QuerySet, dict[str, Any]], CategorySeoBundle]
FilterParser = Callable[[QueryDict], dict]
FilterApplier = Callable[[QuerySet, dict], QuerySet]


@dataclass
class CategoryPagination:
    page_obj: Any
    paginator: Paginator
    query_string: str

    @property
    def has_next(self) -> bool:
        return self.page_obj.has_next()

    @property
    def has_prev(self) -> bool:
        return self.page_obj.has_previous()


@dataclass
class CategoryHeroContext:
    show_category_hero: bool
    hero_title: str
    hero_subtitle: str
    page_header_title_tag: str
    hero_cta_label: str = "Publicar anuncio"


def _hero_from_seo(bundle: CategorySeoBundle) -> CategoryHeroContext:
    return CategoryHeroContext(
        show_category_hero=bundle.show_category_hero,
        hero_title=bundle.hero_title,
        hero_subtitle=bundle.hero_subtitle,
        page_header_title_tag=bundle.page_header_title_tag,
    )


def _category_hero_cta_label(category: Any | None) -> str:
    slug = getattr(category, "slug", "")
    return CATEGORY_HERO_CTA_LABELS.get(slug, "Publicar anuncio")


@dataclass
class CategoryPageContext:
    """Contrato único del runtime de listados (browse, hub, location)."""

    queryset: QuerySet
    filters: dict[str, Any]
    seo: CategorySeoBundle
    hero: CategoryHeroContext
    pagination: CategoryPagination
    category: Any | None
    template: str
    search_query: str
    location_context: dict[str, Any] = field(default_factory=dict)
    cards_context: dict[str, Any] = field(default_factory=dict)
    template_extras: dict[str, Any] = field(default_factory=dict)
    featured_cards: list[Any] = field(default_factory=list)
    normal_cards: list[Any] = field(default_factory=list)
    suggestion_cards: list[Any] = field(default_factory=list)
    listings_meta_robots: str | None = None
    results_count: int = 0

    def render_dict(self) -> dict[str, Any]:
        b = self.seo
        h = self.hero
        p = self.pagination
        out: dict[str, Any] = {
            "category": self.category,
            "meta_title": b.meta_title,
            "meta_description": b.meta_description,
            "canonical_href_override": b.canonical_href,
            "show_category_hero": h.show_category_hero,
            "hero_title": h.hero_title,
            "hero_subtitle": h.hero_subtitle,
            "hero_cta_label": _category_hero_cta_label(self.category),
            "page_header_title_tag": h.page_header_title_tag,
            "list_heading": b.list_heading,
            "list_subtitle": b.list_subtitle,
            "dynamic_list_heading": b.dynamic_list_heading,
            "page_obj": p.page_obj,
            "pagination_query": p.query_string,
            "result_count": p.paginator.count,
            "results_count": self.results_count,
            "pager_has_next": p.has_next,
            "pager_has_prev": p.has_prev,
        }
        out.update(self.location_context)
        out.update(self.cards_context)
        out["template_extras"] = self.template_extras
        out["featured_cards"] = self.featured_cards
        out["normal_cards"] = self.normal_cards
        out["suggestion_cards"] = self.suggestion_cards
        if self.listings_meta_robots:
            out["listings_meta_robots"] = self.listings_meta_robots
        return out


def get_category_contract(slug: str) -> CategoryContractSpec | None:
    return CATEGORY_CONTRACT_REGISTRY.get(slug)


def get_category_behavior(slug: str) -> CategoryContractSpec | None:
    return get_category_contract(slug)


get_category_behavior_spec = get_category_contract


def apply_search(
    qs: QuerySet,
    q_raw: str,
    category_slug: str | None = None,
) -> QuerySet:
    """
    Búsqueda por q: única API pública del engine (título, descripción, campos por categoría).
    """
    q_raw = (q_raw or "").strip()
    if not q_raw:
        return qs
    text_q = Q(title__icontains=q_raw) | Q(description__icontains=q_raw)
    slug = (category_slug or "").strip() or None
    if not slug:
        return qs.filter(
            text_q
            | Q(vehicle__brand_fk__name__icontains=q_raw)
            | Q(vehicle__model_fk__name__icontains=q_raw)
            | Q(vehicle__brand__icontains=q_raw)
            | Q(vehicle__model__icontains=q_raw)
            | Q(motorcycle__brand__icontains=q_raw)
            | Q(motorcycle__model__icontains=q_raw)
            | Q(electronics__brand__icontains=q_raw)
            | Q(electronics__model__icontains=q_raw)
            | Q(homegoods__brand__icontains=q_raw)
            | Q(homegoods__material__icontains=q_raw)
        )
    if slug == VEHICLE_SLUG:
        return qs.filter(
            text_q
            | Q(vehicle__brand_fk__name__icontains=q_raw)
            | Q(vehicle__model_fk__name__icontains=q_raw)
            | Q(vehicle__brand__icontains=q_raw)
            | Q(vehicle__model__icontains=q_raw)
        )
    if slug == MOTORCYCLE_SLUG:
        return qs.filter(
            text_q
            | Q(motorcycle__brand__icontains=q_raw)
            | Q(motorcycle__model__icontains=q_raw)
        )
    if slug == PROPERTY_SLUG:
        return qs.filter(
            text_q
            | Q(property__property_type__icontains=q_raw)
            | Q(property__operation_type__icontains=q_raw)
        )
    if slug == ELECTRONICS_SLUG:
        return qs.filter(
            text_q
            | Q(electronics__brand__icontains=q_raw)
            | Q(electronics__model__icontains=q_raw)
        )
    if slug == HOMEGOODS_SLUG:
        return qs.filter(
            text_q
            | Q(homegoods__brand__icontains=q_raw)
            | Q(homegoods__material__icontains=q_raw)
        )
    return qs.filter(text_q)


def apply_category_pipeline(
    request: HttpRequest,
    qs: QuerySet,
    category_slug: str,
    *,
    scope: str = "hub",
) -> tuple[QuerySet, dict, str]:
    """
    Pipeline fijo (hub / listado ya acotado a categoría):
    1) QueryPlan  2) búsqueda q  3) filtros  4) orden.
    """
    _ = scope
    q_raw = (request.GET.get("q") or "").strip()
    contract = get_category_contract(category_slug)
    if contract is None:
        raise ImproperlyConfigured(
            f"apply_category_pipeline: falta CategoryContractSpec para {category_slug!r}",
        )
    cache_key = f"hub:{category_slug}"
    ext_plan = get_cached_query_plan(
        request,
        cache_key,
        lambda: contract.query_plan_builder(
            request,
            {"scope": "hub", "category_slug": category_slug},
        ),
    )
    plan = merge_query_plans(LISTING_LIST_BASE_PLAN, ext_plan)
    qs = apply_query_plan(qs, plan)
    qs = apply_search(qs, q_raw, category_slug)
    if contract.filter_parser is not None and contract.filter_applier is not None:
        parsed = contract.filter_parser(request.GET)
        qs = contract.filter_applier(qs, parsed)
    else:
        parsed = {}
    qs = apply_listing_order(qs, parse_sort_param(request))
    return qs, parsed, q_raw


def build_category_queryset(
    request: HttpRequest,
    qs: QuerySet,
    category_slug: str,
) -> tuple[QuerySet, dict, str]:
    """Alias del pipeline hub (enrichment completo)."""
    return apply_category_pipeline(request, qs, category_slug, scope="hub")


def _browse_preserved_query_params(request: HttpRequest) -> QueryDict:
    """Query de /anuncios/ sin category ni page (para redirigir al hub canónico)."""
    params = request.GET.copy()
    params.pop("category", None)
    params.pop("page", None)
    return params


def browse_category_hub_href(request: HttpRequest, category_slug: str) -> str:
    """
    URL canónica de una categoría desde browse, preservando q/location/filtros.
    /autos/, /guayaquil/autos/, etc.
    """
    params = _browse_preserved_query_params(request)
    location_slug = (params.get("location") or "").strip()
    if location_slug and location_slug in LOCATION_LANDING_CONFIG:
        contract = get_category_contract(category_slug)
        if contract and contract.allowed_location_mode == "city+category":
            params.pop("location", None)
            url_name = {
                "guayaquil": "location_guayaquil_category",
                "samborondon": "location_samborondon_category",
            }.get(location_slug)
            if url_name:
                url = reverse(url_name, kwargs={"category_slug": category_slug})
                qs = params.urlencode()
                return f"{url}?{qs}" if qs else url
    url = reverse("category_landing", kwargs={"slug": category_slug})
    qs = params.urlencode()
    return f"{url}?{qs}" if qs else url


def browse_category_canonical_redirect(
    request: HttpRequest,
) -> HttpResponseRedirect | None:
    """
    301 /anuncios/?category=autos → /autos/ (o /guayaquil/autos/ si aplica).
    Evita duplicar contenido SEO frente a los hubs de categoría.
    """
    category_slug = (request.GET.get("category") or "").strip()
    if not category_slug:
        return None
    if not Category.objects.filter(slug=category_slug).exists():
        return None
    return redirect(browse_category_hub_href(request, category_slug), permanent=True)


def build_browse_listings_queryset(request: HttpRequest) -> QuerySet:
    """Queryset de /anuncios/ con plan ORM centralizado (tests y diagnóstico)."""
    qs = Listing.objects.published()
    qs = apply_query_plan(qs, browse_listings_query_plan(request))
    return qs


def apply_category_filters(
    category_slug: str,
    qs: QuerySet,
    request: HttpRequest,
) -> tuple[QuerySet, dict]:
    spec = get_category_contract(category_slug)
    if spec and spec.filter_parser and spec.filter_applier:
        parsed = spec.filter_parser(request.GET)
        return spec.filter_applier(qs, parsed), parsed
    return qs, {}


def apply_category_search(
    category_slug: str | None,
    qs: QuerySet,
    q_raw: str,
) -> QuerySet:
    return apply_search(qs, q_raw, category_slug)


def resolve_listing_card_template_path(listing: Listing) -> str:
    spec = get_category_contract(listing.category.slug)
    if spec is not None:
        return spec.card_template
    return LISTING_CARD_DTO_UNIFIED


def _paginate(request: HttpRequest, qs: QuerySet) -> tuple[Any, Paginator, str]:
    params = request.GET.copy()
    if "page" in params:
        params.pop("page")
    pagination_query = params.urlencode()
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page") or 1)
    return page, paginator, pagination_query


def _split_listings_page_bundle(
    request: HttpRequest,
    qs: QuerySet,
    *,
    filters_active: bool,
    clear_listings_href: str,
) -> dict[str, Any]:
    """
    Destacados (no paginados, máx. N) + listado principal paginado sobre el mismo queryset ordenado.
    Los IDs del bloque destacado se omiten en las cards del listado principal (sin tocar el ORM).
    Vacíos inteligentes, sugerencias globales si hay filtros, robots noindex si no hay resultados.
    """
    from .listing_card_dto import build_listing_cards_for_listings
    from .listing_sort import split_featured_block

    featured_qs, normal_qs = split_featured_block(qs)
    featured_rows = list(featured_qs)
    page, paginator, pagination_query = _paginate(request, normal_qs)
    normal_rows = list(page.object_list)

    seller_ids: set[int] = set()
    for row in featured_rows + normal_rows:
        seller_ids.add(row.seller_id)
    trust_map = bulk_seller_trust(list(seller_ids))

    feat_pks = frozenset(int(r.pk) for r in featured_rows if r.pk)
    featured_cards = build_listing_cards_for_listings(
        featured_rows,
        trust_map=trust_map,
        featured_top_ids=feat_pks,
    )
    normal_cards = build_listing_cards_for_listings(
        normal_rows,
        trust_map=trust_map,
        featured_top_ids=frozenset(),
    )
    featured_ids_render = {c.listing_id for c in featured_cards}
    normal_cards = [
        c for c in normal_cards if c.listing_id not in featured_ids_render
    ]

    suggestion_cards: list[Any] = []
    listings_meta_robots: str | None = None
    listings_render: dict[str, Any] = {}

    if paginator.count == 0:
        listings_meta_robots = "noindex, follow"

    if paginator.count == 0 and page.number == 1:
        listings_render["listings_results_empty"] = True
        listings_render["listings_empty_title"] = "No encontramos resultados"
        listings_render["listings_empty_description"] = (
            "Probá quitar filtros o ampliar la búsqueda."
        )
        listings_render["listings_empty_cta_label"] = "Ver todos"
        listings_render["listings_empty_cta_href"] = clear_listings_href
        hints = ["Quitá filtros o cambiá el criterio de orden."]
        if featured_rows:
            hints.append(
                "Los destacados aparecen arriba: revisalos en la sección «Destacados».",
            )
        listings_render["listings_empty_hints"] = hints
        if filters_active:
            fb_rows = list(
                Listing.objects.published()
                .select_related("seller", "category")
                .prefetch_related("images")
                .order_by("-created_at")[:12],
            )
            if fb_rows:
                s2 = {r.seller_id for r in fb_rows}
                trust_merged = bulk_seller_trust(list(seller_ids | s2))
                suggestion_cards = build_listing_cards_for_listings(
                    fb_rows,
                    trust_map=trust_merged,
                    featured_top_ids=frozenset(),
                )
                listings_render["listings_suggestions_heading"] = "Sugerencias"

    return {
        "featured_cards": featured_cards,
        "normal_cards": normal_cards,
        "suggestion_cards": suggestion_cards,
        "page": page,
        "paginator": paginator,
        "pagination_query": pagination_query,
        "listings_meta_robots": listings_meta_robots,
        "listings_render": listings_render,
        "listing_cards_alias": normal_cards,
    }


def _seo_ctx_base(
    *,
    brand: str,
    city: str,
    category,
    parsed: dict,
    result_count: int,
    q_raw: str,
    filters_active: bool,
    frame: str,
    location_display: str | None = None,
    location_slug: str = "",
    browse_location_slug: str = "",
) -> dict[str, Any]:
    return {
        "frame": frame,
        "brand": brand,
        "city": city,
        "category": category,
        "parsed": parsed,
        "result_count": result_count,
        "q_raw": q_raw,
        "filters_active": filters_active,
        "location_display": location_display,
        "location_slug": location_slug,
        "browse_location_slug": browse_location_slug,
    }


def _build_seo_bundle(
    request: HttpRequest,
    category_slug: str,
    qs: QuerySet,
    *,
    frame: str,
    brand: str,
    city: str,
    category,
    parsed: dict,
    result_count: int,
    q_raw: str,
    filters_active: bool,
    location_display: str | None = None,
    location_slug: str = "",
    browse_location_slug: str = "",
) -> CategorySeoBundle:
    """Ensambla meta/h1/canónica sin normalizar URL absoluta (uso interno)."""
    slug = (category_slug or "").strip()
    ctx = _seo_ctx_base(
        brand=brand,
        city=city,
        category=category,
        parsed=parsed,
        result_count=result_count,
        q_raw=q_raw,
        filters_active=filters_active,
        frame=frame,
        location_display=location_display,
        location_slug=location_slug,
        browse_location_slug=browse_location_slug,
    )
    if frame == "browse":
        if (
            slug
            in (
                VEHICLE_SLUG,
                PROPERTY_SLUG,
                MOTORCYCLE_SLUG,
                ELECTRONICS_SLUG,
                HOMEGOODS_SLUG,
            )
            and category is not None
        ):
            contract = get_category_contract(slug)
            if contract is None:
                raise ImproperlyConfigured(f"build_seo browse: sin contrato {slug!r}")
            return contract.seo_builder(request, qs, ctx)
        return BROWSE_FRAME_SEO_BUILDER(
            request,
            qs,
            {
                "brand": brand,
                "city": city,
                "category_obj": category,
                "category_slug": slug,
                "result_count": result_count,
                "location_display": location_display,
            },
        )
    if not slug:
        raise ImproperlyConfigured("build_seo: category_slug requerido fuera de frame browse")
    contract = get_category_contract(slug)
    if contract is None:
        raise ImproperlyConfigured(f"build_seo: sin CategoryContractSpec para {slug!r}")
    return contract.seo_builder(request, qs, ctx)


def _ensure_canonical_absolute(request: HttpRequest, bundle: CategorySeoBundle) -> None:
    ch = (bundle.canonical_href or "").strip()
    if ch.startswith("http://") or ch.startswith("https://"):
        return
    if ch.startswith("/"):
        bundle.canonical_href = request.build_absolute_uri(ch)
        return
    bundle.canonical_href = request.build_absolute_uri(request.path)


def build_category_seo_context(
    request: HttpRequest,
    category_slug: str,
    qs: QuerySet,
    *,
    frame: str,
    brand: str,
    city: str,
    category,
    parsed: dict,
    result_count: int,
    q_raw: str,
    filters_active: bool,
    location_display: str | None = None,
    location_slug: str = "",
    browse_location_slug: str = "",
) -> CategorySeoBundle:
    """
    Única API pública del engine para SEO de listados (browse / hub / ciudad).
    Garantiza canónica absoluta.
    """
    bundle = _build_seo_bundle(
        request,
        category_slug,
        qs,
        frame=frame,
        brand=brand,
        city=city,
        category=category,
        parsed=parsed,
        result_count=result_count,
        q_raw=q_raw,
        filters_active=filters_active,
        location_display=location_display,
        location_slug=location_slug,
        browse_location_slug=browse_location_slug,
    )
    _ensure_canonical_absolute(request, bundle)
    return bundle


def build_seo(
    request: HttpRequest,
    category_slug: str,
    qs: QuerySet,
    *,
    frame: str,
    brand: str,
    city: str,
    category,
    parsed: dict,
    result_count: int,
    q_raw: str,
    filters_active: bool,
    location_display: str | None = None,
    location_slug: str = "",
    browse_location_slug: str = "",
) -> CategorySeoBundle:
    """Alias de `build_category_seo_context` (compat)."""
    return build_category_seo_context(
        request,
        category_slug,
        qs,
        frame=frame,
        brand=brand,
        city=city,
        category=category,
        parsed=parsed,
        result_count=result_count,
        q_raw=q_raw,
        filters_active=filters_active,
        location_display=location_display,
        location_slug=location_slug,
        browse_location_slug=browse_location_slug,
    )


def _page_context_browse(request: HttpRequest) -> CategoryPageContext:
    qs = build_browse_listings_queryset(request)
    q_raw = (request.GET.get("q") or "").strip()
    location_slug = (request.GET.get("location") or "").strip()

    qs = apply_search(qs, q_raw, None)

    if location_slug:
        cfg = LOCATION_LANDING_CONFIG.get(location_slug)
        if cfg:
            q_loc = Q()
            for needle in cfg["needles"]:
                q_loc |= Q(location__icontains=needle)
            qs = qs.filter(q_loc)
        else:
            qs = qs.filter(location__icontains=location_slug)

    sort = parse_sort_param(request)
    qs = apply_listing_order(qs, sort)
    lb = _split_listings_page_bundle(
        request,
        qs,
        filters_active=bool(q_raw or location_slug),
        clear_listings_href=reverse("browse"),
    )
    page = lb["page"]
    paginator = lb["paginator"]
    pagination_query = lb["pagination_query"]

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    location_display: str | None = None
    if location_slug:
        loc_cfg = LOCATION_LANDING_CONFIG.get(location_slug)
        if loc_cfg:
            location_display = loc_cfg["display"]

    bundle = build_seo(
        request,
        "",
        qs,
        frame="browse",
        brand=brand,
        city=city,
        category=None,
        parsed={},
        result_count=paginator.count,
        q_raw=q_raw,
        filters_active=bool(q_raw or location_slug),
        location_display=location_display,
        browse_location_slug=location_slug,
    )

    clear_params: dict = {}
    if q_raw:
        clear_params["q"] = q_raw
    if location_slug:
        clear_params["location"] = location_slug
    category_filter_clear_url = reverse("browse")
    if clear_params:
        category_filter_clear_url = f"{category_filter_clear_url}?{urlencode(clear_params)}"

    location_ctx: dict[str, Any] = {}
    if location_slug:
        location_ctx["browse_location_slug"] = location_slug
        loc_cfg = LOCATION_LANDING_CONFIG.get(location_slug)
        if loc_cfg:
            location_ctx["location_display"] = loc_cfg["display"]

    cards_ctx: dict[str, Any] = {
        "browse_has_sidebar_filters": True,
        "filter_panel_kind": "category",
        "category_filter_options": [
            {
                "slug": cat.slug,
                "name": cat.name,
                "href": browse_category_hub_href(request, cat.slug),
            }
            for cat in root_categories()
        ],
        "category_filter_selected": "",
        "category_filter_clear_url": category_filter_clear_url,
    }
    cards_ctx["listing_cards"] = lb["listing_cards_alias"]
    cards_ctx.update(lb["listings_render"])

    return CategoryPageContext(
        queryset=qs,
        filters={},
        seo=bundle,
        hero=_hero_from_seo(bundle),
        category=None,
        template=BROWSE_TEMPLATE_LIST,
        pagination=CategoryPagination(page, paginator, pagination_query),
        search_query=q_raw,
        location_context=location_ctx,
        cards_context=cards_ctx,
        template_extras=build_sort_template_extras(request, current_sort=sort),
        featured_cards=lb["featured_cards"],
        normal_cards=lb["normal_cards"],
        suggestion_cards=lb["suggestion_cards"],
        listings_meta_robots=lb["listings_meta_robots"],
        results_count=paginator.count,
    )


def _page_context_hub(request: HttpRequest, category) -> CategoryPageContext:
    from .models import ItemCondition, MotorcycleListing, VehicleBrand, VehicleListing

    slug = category.slug
    if get_category_contract(slug) is None:
        raise Http404()
    qs = Listing.objects.published().filter(category=category)
    qs, parsed, q_raw = build_category_queryset(request, qs, slug)
    sort = parse_sort_param(request)

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    intro = (
        f"Encuentra {category.name.lower()} en venta en {city} de forma segura. "
        f"Contacta vendedores verificados y evita estafas."
    )

    show_autos = slug == VEHICLE_SLUG
    show_property = slug == PROPERTY_SLUG
    show_moto = slug == MOTORCYCLE_SLUG
    show_electronics = slug == ELECTRONICS_SLUG
    show_home = slug == HOMEGOODS_SLUG

    filters_active = (
        show_autos and listing_services.vehicle_browse_filters_active(parsed)
    ) or (
        show_property and listing_services.property_browse_filters_active(parsed)
    ) or (
        show_moto and listing_services.motorcycle_browse_filters_active(parsed)
    ) or (
        show_electronics and listing_services.electronics_browse_filters_active(parsed)
    ) or (show_home and listing_services.home_browse_filters_active(parsed))

    filter_clear_url = reverse("category_landing", kwargs={"slug": slug})
    lb = _split_listings_page_bundle(
        request,
        qs,
        filters_active=filters_active,
        clear_listings_href=filter_clear_url,
    )
    page = lb["page"]
    paginator = lb["paginator"]
    pagination_query = lb["pagination_query"]

    seo_parsed = (
        parsed
        if (show_autos or show_property or show_moto or show_electronics or show_home)
        else {}
    )
    bundle = build_seo(
        request,
        slug,
        qs,
        frame="hub",
        brand=brand,
        city=city,
        category=category,
        parsed=seo_parsed,
        result_count=paginator.count,
        q_raw=q_raw,
        filters_active=filters_active,
    )

    browse_brands = VehicleBrand.objects.order_by("name") if show_autos else None
    browse_model_choices = (
        listing_services.vehicle_model_options_for_browse(parsed.get("marca_id"))
        if show_autos
        else []
    )

    filter_panel_kind = ""
    if show_autos:
        filter_panel_kind = "vehicle"
    elif show_property:
        filter_panel_kind = "property"
    elif show_moto:
        filter_panel_kind = "motorcycle"
    elif show_electronics:
        filter_panel_kind = "electronics"
    elif show_home:
        filter_panel_kind = "home"

    loc_ctx: dict[str, Any] = {
        "browse_h1": bundle.browse_h1,
        "browse_intro": intro,
    }
    cards_ctx: dict[str, Any] = {
        "browse_has_sidebar_filters": bool(filter_panel_kind),
        "filter_panel_kind": filter_panel_kind,
        "show_autos_category_crosslink": slug != VEHICLE_SLUG,
        "show_autos_filters": show_autos,
        "show_property_filters": show_property,
        "show_motorcycle_filters": show_moto,
        "show_electronics_filters": show_electronics,
        "show_home_filters": show_home,
        "vehicle_filter_params": parsed if show_autos else {},
        "property_filter_params": parsed if show_property else {},
        "motorcycle_filter_params": parsed if show_moto else {},
        "electronics_filter_params": parsed if show_electronics else {},
        "home_filter_params": parsed if show_home else {},
        "browse_brands": browse_brands,
        "browse_model_choices": browse_model_choices,
        "vehicle_transmission_choices": VehicleListing.Transmission.choices,
        "motorcycle_transmission_choices": MotorcycleListing.Transmission.choices,
        "motorcycle_fuel_choices": MotorcycleListing.FuelType.choices,
        "motorcycle_condition_choices": ItemCondition.choices,
        "electronics_condition_choices": ItemCondition.choices,
        "home_item_type_choices": listing_services.home_item_type_choices_tuple(),
        "home_condition_choices": ItemCondition.choices,
        "filter_clear_url": filter_clear_url,
        "selected_filters": parsed
        if (show_autos or show_property or show_moto or show_electronics or show_home)
        else {},
        "vehicle_filters_form_action": "",
        "vehicle_filters_include_category": False,
        "property_filters_form_action": "",
        "property_filters_include_category": False,
        "motorcycle_filters_form_action": "",
        "motorcycle_filters_include_category": False,
        "electronics_filters_form_action": "",
        "electronics_filters_include_category": False,
        "home_filters_form_action": "",
        "home_filters_include_category": False,
    }
    cards_ctx["listing_cards"] = lb["listing_cards_alias"]
    cards_ctx.update(lb["listings_render"])

    return CategoryPageContext(
        queryset=qs,
        filters=parsed,
        seo=bundle,
        hero=_hero_from_seo(bundle),
        category=category,
        template=BROWSE_TEMPLATE_CATEGORY,
        pagination=CategoryPagination(page, paginator, pagination_query),
        search_query=q_raw,
        location_context=loc_ctx,
        cards_context=cards_ctx,
        template_extras=build_sort_template_extras(request, current_sort=sort),
        featured_cards=lb["featured_cards"],
        normal_cards=lb["normal_cards"],
        suggestion_cards=lb["suggestion_cards"],
        listings_meta_robots=lb["listings_meta_robots"],
        results_count=paginator.count,
    )


def _page_context_location_hub(
    request: HttpRequest,
    *,
    location_slug: str,
    category,
) -> CategoryPageContext:
    from .models import ItemCondition, MotorcycleListing, VehicleBrand, VehicleListing

    cfg = LOCATION_LANDING_CONFIG.get(location_slug)
    if not cfg:
        raise ValueError("unknown location")
    display = cfg["display"]
    q_loc = Q()
    for needle in cfg["needles"]:
        q_loc |= Q(location__icontains=needle)

    slug = category.slug
    qs = Listing.objects.published().filter(q_loc, category=category)
    qs, parsed, q_raw = build_category_queryset(request, qs, slug)
    sort = parse_sort_param(request)

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")

    show_autos = slug == VEHICLE_SLUG
    show_property = slug == PROPERTY_SLUG
    show_moto = slug == MOTORCYCLE_SLUG
    show_electronics = slug == ELECTRONICS_SLUG
    show_home = slug == HOMEGOODS_SLUG

    filters_active = (
        show_autos and listing_services.vehicle_browse_filters_active(parsed)
    ) or (
        show_property and listing_services.property_browse_filters_active(parsed)
    ) or (
        show_moto and listing_services.motorcycle_browse_filters_active(parsed)
    ) or (
        show_electronics and listing_services.electronics_browse_filters_active(parsed)
    ) or (show_home and listing_services.home_browse_filters_active(parsed))

    if location_slug == "guayaquil":
        filter_clear_url = reverse(
            "location_guayaquil_category",
            kwargs={"category_slug": category.slug},
        )
    elif location_slug == "samborondon":
        filter_clear_url = reverse(
            "location_samborondon_category",
            kwargs={"category_slug": category.slug},
        )
    else:
        filter_clear_url = request.path

    lb = _split_listings_page_bundle(
        request,
        qs,
        filters_active=filters_active,
        clear_listings_href=filter_clear_url,
    )
    page = lb["page"]
    paginator = lb["paginator"]
    pagination_query = lb["pagination_query"]

    bundle = build_seo(
        request,
        slug,
        qs,
        frame="location_hub",
        brand=brand,
        city=city,
        category=category,
        parsed=parsed,
        result_count=paginator.count,
        q_raw=q_raw,
        filters_active=filters_active,
        location_display=display,
        location_slug=location_slug,
    )

    browse_brands = VehicleBrand.objects.order_by("name") if show_autos else None
    browse_model_choices = (
        listing_services.vehicle_model_options_for_browse(parsed.get("marca_id"))
        if show_autos
        else []
    )

    filter_panel_kind = ""
    if show_autos:
        filter_panel_kind = "vehicle"
    elif show_property:
        filter_panel_kind = "property"
    elif show_moto:
        filter_panel_kind = "motorcycle"
    elif show_electronics:
        filter_panel_kind = "electronics"
    elif show_home:
        filter_panel_kind = "home"

    loc_ctx: dict[str, Any] = {
        "location_slug": location_slug,
        "location_display": display,
    }
    cards_ctx: dict[str, Any] = {
        "browse_has_sidebar_filters": bool(filter_panel_kind),
        "filter_panel_kind": filter_panel_kind,
        "show_autos_filters": show_autos,
        "show_property_filters": show_property,
        "show_motorcycle_filters": show_moto,
        "show_electronics_filters": show_electronics,
        "show_home_filters": show_home,
        "vehicle_filter_params": parsed if show_autos else {},
        "property_filter_params": parsed if show_property else {},
        "motorcycle_filter_params": parsed if show_moto else {},
        "electronics_filter_params": parsed if show_electronics else {},
        "home_filter_params": parsed if show_home else {},
        "browse_brands": browse_brands,
        "browse_model_choices": browse_model_choices,
        "vehicle_transmission_choices": VehicleListing.Transmission.choices,
        "motorcycle_transmission_choices": MotorcycleListing.Transmission.choices,
        "motorcycle_fuel_choices": MotorcycleListing.FuelType.choices,
        "motorcycle_condition_choices": ItemCondition.choices,
        "electronics_condition_choices": ItemCondition.choices,
        "home_item_type_choices": listing_services.home_item_type_choices_tuple(),
        "home_condition_choices": ItemCondition.choices,
        "filter_clear_url": filter_clear_url,
        "selected_filters": parsed
        if (show_autos or show_property or show_moto or show_electronics or show_home)
        else {},
        "vehicle_filters_form_action": "",
        "vehicle_filters_include_category": False,
        "property_filters_form_action": "",
        "property_filters_include_category": False,
        "motorcycle_filters_form_action": "",
        "motorcycle_filters_include_category": False,
        "electronics_filters_form_action": "",
        "electronics_filters_include_category": False,
        "home_filters_form_action": "",
        "home_filters_include_category": False,
        "show_category_hero": True,
        "page_header_title_tag": "h2",
    }
    cards_ctx["listing_cards"] = lb["listing_cards_alias"]
    cards_ctx.update(lb["listings_render"])

    return CategoryPageContext(
        queryset=qs,
        filters=parsed,
        seo=bundle,
        hero=_hero_from_seo(bundle),
        category=category,
        template=BROWSE_TEMPLATE_LIST,
        pagination=CategoryPagination(page, paginator, pagination_query),
        search_query=q_raw,
        location_context=loc_ctx,
        cards_context=cards_ctx,
        template_extras=build_sort_template_extras(request, current_sort=sort),
        featured_cards=lb["featured_cards"],
        normal_cards=lb["normal_cards"],
        suggestion_cards=lb["suggestion_cards"],
        listings_meta_robots=lb["listings_meta_robots"],
        results_count=paginator.count,
    )


def _page_context_location_only(
    request: HttpRequest,
    *,
    location_slug: str,
) -> CategoryPageContext:
    from .models import ItemCondition, MotorcycleListing, VehicleListing

    cfg = LOCATION_LANDING_CONFIG[location_slug]
    display = cfg["display"]
    q_loc = Q()
    for needle in cfg["needles"]:
        q_loc |= Q(location__icontains=needle)

    q_raw = (request.GET.get("q") or "").strip()
    qs = Listing.objects.published().filter(q_loc)
    qs = apply_query_plan(qs, LISTING_LIST_BASE_PLAN)
    qs = apply_search(qs, q_raw, None)
    sort = parse_sort_param(request)
    qs = apply_listing_order(qs, sort)
    lb = _split_listings_page_bundle(
        request,
        qs,
        filters_active=False,
        clear_listings_href=reverse("browse"),
    )
    page = lb["page"]
    paginator = lb["paginator"]
    pagination_query = lb["pagination_query"]

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    bundle = seo_location_market(display=display, city=city, brand=brand)
    _ensure_canonical_absolute(request, bundle)

    loc_ctx: dict[str, Any] = {
        "browse_h1": bundle.browse_h1,
        "browse_intro": bundle.meta_description,
        "location_slug": location_slug,
        "location_display": display,
    }
    cards_ctx: dict[str, Any] = {
        "browse_has_sidebar_filters": False,
        "filter_panel_kind": "",
        "show_autos_filters": False,
        "show_property_filters": False,
        "show_motorcycle_filters": False,
        "show_electronics_filters": False,
        "show_home_filters": False,
        "vehicle_filter_params": {},
        "property_filter_params": {},
        "motorcycle_filter_params": {},
        "electronics_filter_params": {},
        "home_filter_params": {},
        "browse_brands": None,
        "browse_model_choices": [],
        "vehicle_transmission_choices": VehicleListing.Transmission.choices,
        "motorcycle_transmission_choices": MotorcycleListing.Transmission.choices,
        "motorcycle_fuel_choices": MotorcycleListing.FuelType.choices,
        "motorcycle_condition_choices": ItemCondition.choices,
        "electronics_condition_choices": ItemCondition.choices,
        "home_item_type_choices": listing_services.home_item_type_choices_tuple(),
        "home_condition_choices": ItemCondition.choices,
        "filter_clear_url": "",
        "selected_filters": {},
        "vehicle_filters_form_action": "",
        "vehicle_filters_include_category": False,
        "property_filters_form_action": "",
        "property_filters_include_category": False,
        "motorcycle_filters_form_action": "",
        "motorcycle_filters_include_category": False,
        "electronics_filters_form_action": "",
        "electronics_filters_include_category": False,
        "home_filters_form_action": "",
        "home_filters_include_category": False,
    }
    cards_ctx["listing_cards"] = lb["listing_cards_alias"]
    cards_ctx.update(lb["listings_render"])

    return CategoryPageContext(
        queryset=qs,
        filters={},
        seo=bundle,
        hero=_hero_from_seo(bundle),
        category=None,
        template=BROWSE_TEMPLATE_CATEGORY,
        pagination=CategoryPagination(page, paginator, pagination_query),
        search_query=q_raw,
        location_context=loc_ctx,
        cards_context=cards_ctx,
        template_extras=build_sort_template_extras(request, current_sort=sort),
        featured_cards=lb["featured_cards"],
        normal_cards=lb["normal_cards"],
        suggestion_cards=lb["suggestion_cards"],
        listings_meta_robots=lb["listings_meta_robots"],
        results_count=paginator.count,
    )


def build_category_page(
    request: HttpRequest,
    category_slug: str | None = None,
    location_slug: str | None = None,
) -> CategoryPageContext:
    """
    Único entrypoint de páginas de listado: browse, hub de categoría, landing por ciudad,
    o ciudad + categoría. El contrato de render es siempre `CategoryPageContext.render_dict()`.
    """
    cat_slug = (category_slug or "").strip() or None
    loc_slug = (location_slug or "").strip() or None

    if loc_slug and cat_slug:
        if loc_slug not in LOCATION_LANDING_CONFIG:
            raise Http404()
        category = get_object_or_404(Category, slug=cat_slug)
        ctr = get_category_contract(category.slug)
        if ctr is None or ctr.allowed_location_mode != "city+category":
            raise Http404()
        return _page_context_location_hub(
            request,
            location_slug=loc_slug,
            category=category,
        )
    if loc_slug and not cat_slug:
        if loc_slug not in LOCATION_LANDING_CONFIG:
            raise Http404()
        return _page_context_location_only(request, location_slug=loc_slug)
    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug)
        return _page_context_hub(request, category)
    return _page_context_browse(request)


_VFK = tuple(listing_services.VEHICLE_FILTER_GET_KEYS)
_PFK = tuple(listing_services.PROPERTY_FILTER_GET_KEYS)
_MFK = tuple(listing_services.MOTORCYCLE_FILTER_GET_KEYS)
_EFK = tuple(listing_services.ELECTRONICS_FILTER_GET_KEYS)
_HFK = tuple(listing_services.HOME_FILTER_GET_KEYS)

CATEGORY_CONTRACT_REGISTRY: dict[str, CategoryContractSpec] = {
    VEHICLE_SLUG: CategoryContractSpec(
        slug=VEHICLE_SLUG,
        required_filters=_VFK,
        supported_search_fields=frozenset({"title", "description", "vehicle"}),
        card_template=LISTING_CARD_DTO_UNIFIED,
        seo_builder=seo_vehicle,
        allowed_location_mode="city+category",
        query_plan_builder=hub_vehicle_query_plan,
        filter_get_keys=_VFK,
        filter_parser=listing_services.parse_vehicle_list_filter_params,
        filter_applier=listing_services.apply_vehicle_list_filters,
    ),
    PROPERTY_SLUG: CategoryContractSpec(
        slug=PROPERTY_SLUG,
        required_filters=_PFK,
        supported_search_fields=frozenset({"title", "description", "property"}),
        card_template=LISTING_CARD_DTO_UNIFIED,
        seo_builder=seo_property,
        allowed_location_mode="city+category",
        query_plan_builder=hub_property_query_plan,
        filter_get_keys=_PFK,
        filter_parser=listing_services.parse_property_list_filter_params,
        filter_applier=listing_services.apply_property_list_filters,
    ),
    MOTORCYCLE_SLUG: CategoryContractSpec(
        slug=MOTORCYCLE_SLUG,
        required_filters=_MFK,
        supported_search_fields=frozenset({"title", "description", "motorcycle"}),
        card_template=LISTING_CARD_DTO_UNIFIED,
        seo_builder=seo_motorcycle,
        allowed_location_mode="city+category",
        query_plan_builder=hub_motorcycle_query_plan,
        filter_get_keys=_MFK,
        filter_parser=listing_services.parse_motorcycle_list_filter_params,
        filter_applier=listing_services.apply_motorcycle_list_filters,
    ),
    ELECTRONICS_SLUG: CategoryContractSpec(
        slug=ELECTRONICS_SLUG,
        required_filters=_EFK,
        supported_search_fields=frozenset({"title", "description", "electronics"}),
        card_template=LISTING_CARD_DTO_UNIFIED,
        seo_builder=seo_electronics,
        allowed_location_mode="city+category",
        query_plan_builder=hub_electronics_query_plan,
        filter_get_keys=_EFK,
        filter_parser=listing_services.parse_electronics_list_filter_params,
        filter_applier=listing_services.apply_electronics_list_filters,
    ),
    HOMEGOODS_SLUG: CategoryContractSpec(
        slug=HOMEGOODS_SLUG,
        required_filters=_HFK,
        supported_search_fields=frozenset({"title", "description", "homegoods"}),
        card_template=LISTING_CARD_DTO_UNIFIED,
        seo_builder=seo_home,
        allowed_location_mode="city+category",
        query_plan_builder=hub_home_query_plan,
        filter_get_keys=_HFK,
        filter_parser=listing_services.parse_home_filters,
        filter_applier=listing_services.apply_home_filters,
    ),
}

CATEGORY_BEHAVIOR_REGISTRY = CATEGORY_CONTRACT_REGISTRY


def enrich_category_scoped_listing_queryset(
    category_slug: str,
    request: HttpRequest,
    qs: QuerySet,
) -> tuple[QuerySet, dict, str]:
    if category_slug == VEHICLE_SLUG:
        return listing_services.enrich_autos_scoped_listing_queryset(request, qs)
    if category_slug == PROPERTY_SLUG:
        return listing_services.enrich_property_scoped_listing_queryset(request, qs)
    if category_slug == MOTORCYCLE_SLUG:
        return listing_services.enrich_motorcycle_scoped_listing_queryset(request, qs)
    if category_slug == ELECTRONICS_SLUG:
        return listing_services.enrich_electronics_scoped_listing_queryset(request, qs)
    if category_slug == HOMEGOODS_SLUG:
        return listing_services.enrich_home_scoped_queryset(request, qs)
    q_raw = (request.GET.get("q") or "").strip()
    qs = apply_query_plan(qs, LISTING_LIST_BASE_PLAN)
    qs = apply_search(qs, q_raw, category_slug)
    return qs, {}, q_raw


# Compat: código que aún importaba desde category_behavior
def build_category_seo(category_slug: str, context: dict[str, Any]) -> CategorySeoBundle:
    spec = get_category_contract(category_slug)
    if spec is None:
        raise ImproperlyConfigured(f"build_category_seo: sin contrato {category_slug!r}")
    request = context["request"]
    qs = context.get("qs")
    if qs is None:
        qs = Listing.objects.none()
    bundle = spec.seo_builder(request, qs, context)
    _ensure_canonical_absolute(request, bundle)
    return bundle
