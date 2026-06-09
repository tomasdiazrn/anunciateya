"""
Plan de queries del Category Engine: joins, prefetch y annotations centralizados.

Toda optimización ORM de listados debe expresarse como QueryPlan + apply_query_plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .services import (
    ELECTRONICS_FILTER_GET_KEYS,
    HOME_FILTER_GET_KEYS,
)
from .services_promotions import listing_list_base_annotations


@dataclass(frozen=True)
class QueryPlan:
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[str, ...] = ()
    annotations: dict[str, Any] = field(default_factory=dict)
    only_fields: tuple[str, ...] | None = None


def merge_query_plans(*plans: QueryPlan) -> QueryPlan:
    """Combina planes sin duplicar paths (orden estable: primera aparición gana)."""
    sel: list[str] = []
    seen_s: set[str] = set()
    pref: list[str] = []
    seen_p: set[str] = set()
    ann: dict[str, Any] = {}
    only: tuple[str, ...] | None = None
    for p in plans:
        for s in p.select_related:
            if s not in seen_s:
                seen_s.add(s)
                sel.append(s)
        for s in p.prefetch_related:
            if s not in seen_p:
                seen_p.add(s)
                pref.append(s)
        ann.update(p.annotations)
        if p.only_fields is not None:
            only = p.only_fields
    return QueryPlan(
        select_related=tuple(sel),
        prefetch_related=tuple(pref),
        annotations=ann,
        only_fields=only,
    )


def apply_query_plan(qs: QuerySet, plan: QueryPlan) -> QuerySet:
    """Aplica annotate → select_related → prefetch_related → only (si aplica)."""
    if plan.annotations:
        qs = qs.annotate(**plan.annotations)
    if plan.select_related:
        qs = qs.select_related(*plan.select_related)
    if plan.prefetch_related:
        qs = qs.prefetch_related(*plan.prefetch_related)
    if plan.only_fields is not None:
        qs = qs.only(*plan.only_fields)
    return qs


# Base alineada con el listado público histórico (seller, categoría, imágenes).
LISTING_LIST_BASE_PLAN = QueryPlan(
    # seller__verification: needed for card contact CTAs (tel/WhatsApp) without N+1
    select_related=("seller", "seller__verification", "category"),
    prefetch_related=("images",),
    annotations=listing_list_base_annotations(),
)

# Detalle de anuncio: mismas anotaciones que el listado + extensiones 1:1 (una query, sin N+1).
LISTING_DETAIL_EXTENSION_PLAN = merge_query_plans(
    QueryPlan(select_related=("vehicle", "vehicle__brand_fk", "vehicle__model_fk")),
    QueryPlan(select_related=("property",)),
    QueryPlan(select_related=("motorcycle",)),
    QueryPlan(select_related=("electronics",)),
    QueryPlan(select_related=("homegoods",)),
)

LISTING_DETAIL_ORM_PLAN = merge_query_plans(
    LISTING_LIST_BASE_PLAN,
    LISTING_DETAIL_EXTENSION_PLAN,
)


def _q_raw(request: HttpRequest) -> str:
    return (request.GET.get("q") or "").strip()


def _browse_category_slug(request: HttpRequest) -> str:
    return (request.GET.get("category") or "").strip()


def resolve_browse_extension_query_plan(request: HttpRequest) -> QueryPlan:
    """
    /anuncios/: extensiones ORM para el listado mezclado (misma prioridad que el código legado).

    Solo una vertical añade joins por petición, en este orden: autos → inmuebles → motos →
    electrónica → hogar.
    """
    q_raw = _q_raw(request)
    category_slug = _browse_category_slug(request)

    if category_slug == VEHICLE_SLUG or bool(q_raw):
        return QueryPlan(
            select_related=("vehicle", "vehicle__brand_fk", "vehicle__model_fk"),
        )
    if category_slug == PROPERTY_SLUG:
        return QueryPlan(select_related=("property",))
    if category_slug == MOTORCYCLE_SLUG or bool(q_raw):
        return QueryPlan(select_related=("motorcycle",))
    if category_slug == ELECTRONICS_SLUG and (
        bool(q_raw) or any(request.GET.get(k) for k in ELECTRONICS_FILTER_GET_KEYS)
    ):
        return QueryPlan(select_related=("electronics",))
    if category_slug == HOMEGOODS_SLUG and (
        bool(q_raw) or any(request.GET.get(k) for k in HOME_FILTER_GET_KEYS)
    ):
        return QueryPlan(select_related=("homegoods",))
    return QueryPlan()


def get_cached_query_plan(
    request: HttpRequest,
    cache_key: str,
    factory: Any,
) -> QueryPlan:
    """
    Evita recomputar el mismo plan varias veces en un único request.

    `cache_key` debe incluir scope y categoría relevante (p. ej. ``browse:autos``).
    """
    cache = getattr(request, "_queryplan_cache", None)
    if cache is None:
        cache = {}
        setattr(request, "_queryplan_cache", cache)
    if cache_key not in cache:
        cache[cache_key] = factory()
    return cache[cache_key]


def browse_listings_query_plan(request: HttpRequest) -> QueryPlan:
    cache_key = f"browse:{request.GET.urlencode()}"
    return get_cached_query_plan(
        request,
        cache_key,
        lambda: merge_query_plans(
            LISTING_LIST_BASE_PLAN,
            resolve_browse_extension_query_plan(request),
        ),
    )


# —— Hub / ciudad+categoría: extensión siempre cargada (cards DTO sin N+1) ——


def hub_vehicle_query_plan(request: HttpRequest, ctx: dict[str, Any]) -> QueryPlan:
    del request, ctx
    return QueryPlan(select_related=("vehicle", "vehicle__brand_fk", "vehicle__model_fk"))


def hub_property_query_plan(request: HttpRequest, ctx: dict[str, Any]) -> QueryPlan:
    del request, ctx
    return QueryPlan(select_related=("property",))


def hub_motorcycle_query_plan(request: HttpRequest, ctx: dict[str, Any]) -> QueryPlan:
    del request, ctx
    return QueryPlan(select_related=("motorcycle",))


def hub_electronics_query_plan(request: HttpRequest, ctx: dict[str, Any]) -> QueryPlan:
    del request, ctx
    return QueryPlan(select_related=("electronics",))


def hub_home_query_plan(request: HttpRequest, ctx: dict[str, Any]) -> QueryPlan:
    del request, ctx
    return QueryPlan(select_related=("homegoods",))
