"""
Contratos estrictos por categoría (plugins validados al arranque).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal

from django.db.models import QuerySet
from django.http import HttpRequest, QueryDict

if TYPE_CHECKING:
    from .category_engine_queryplan import QueryPlan

LocationMode = Literal["none", "city", "city+category"]

SeoBuilder = Callable[[HttpRequest, QuerySet, dict[str, Any]], Any]
FilterParser = Callable[[QueryDict], dict]
FilterApplier = Callable[[QuerySet, dict], QuerySet]
QueryPlanBuilder = Callable[[HttpRequest, dict[str, Any]], "QueryPlan"]


@dataclass(frozen=True)
class CategoryContractSpec:
    slug: str
    required_filters: tuple[str, ...]
    supported_search_fields: frozenset[str]
    card_template: str
    seo_builder: SeoBuilder
    allowed_location_mode: LocationMode
    query_plan_builder: QueryPlanBuilder
    filter_get_keys: tuple[str, ...] = field(default_factory=tuple)
    filter_parser: FilterParser | None = None
    filter_applier: FilterApplier | None = None
