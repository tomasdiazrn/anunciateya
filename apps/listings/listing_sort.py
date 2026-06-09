"""
Orden de listados públicos (?sort=) y split del bloque destacado vs listado paginado.

El bloque superior usa un slice del mismo queryset; la exclusión visual de duplicados va en cards.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import FieldError
from django.db.models import F, QuerySet
from django.http import HttpRequest

ALLOWED_SORTS = frozenset({"relevance", "newest", "price_asc", "price_desc"})

RELEVANCE_ORDER: tuple[str, ...] = (
    "-has_active_featured",
    "-has_active_boost",
    "-boost_score",
    "-is_featured",
    "-quality_score",
    "-created_at",
)

FEATURED_TOP_LIMIT = 3


def parse_sort_param(request: HttpRequest) -> str:
    raw = (request.GET.get("sort") or "relevance").strip()
    if raw not in ALLOWED_SORTS:
        return "relevance"
    return raw


def apply_listing_order(qs: QuerySet, sort: str) -> QuerySet:
    if sort == "relevance":
        return qs.order_by(*RELEVANCE_ORDER)
    if sort == "newest":
        return qs.order_by("-created_at")
    if sort == "price_asc":
        return qs.order_by(F("price_amount").asc(nulls_last=True))
    if sort == "price_desc":
        return qs.order_by(F("price_amount").desc(nulls_last=True))
    return qs.order_by(*RELEVANCE_ORDER)


def split_featured_block(
    qs: QuerySet,
    *,
    limit: int = FEATURED_TOP_LIMIT,
) -> tuple[QuerySet, QuerySet]:
    """
    Bloque destacado (máx. `limit`) + mismo queryset para resultados paginados.

    - featured_qs: is_featured=1, orden del padre, recortado a N (solo bloque superior).
    - normal_qs: mismo `qs` (incluye destacados); la deduplicación visual va en las cards.
    """
    try:
        featured_qs = qs.filter(is_featured=1)[:limit]
        return featured_qs, qs
    except FieldError:
        return qs.none(), qs


def build_sort_template_extras(request: HttpRequest, *, current_sort: str) -> dict[str, Any]:
    """current_sort y sort_options (value, label, href, selected) para el desplegable de orden."""
    path = request.path
    base_params = request.GET.copy()
    base_params.pop("page", None)
    options: list[dict[str, str]] = []
    for value, label in (
        ("relevance", "Relevantes"),
        ("newest", "Más recientes"),
        ("price_asc", "Menor precio"),
        ("price_desc", "Mayor precio"),
    ):
        p = base_params.copy()
        if value == "relevance":
            p.pop("sort", None)
        else:
            p["sort"] = value
        qs_str = p.urlencode()
        href = f"{path}?{qs_str}" if qs_str else path
        active = value == current_sort
        options.append(
            {
                "value": value,
                "label": label,
                "href": href,
                "selected": active,
            }
        )
    return {
        "current_sort": current_sort,
        "sort_options": options,
    }
