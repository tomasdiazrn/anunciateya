"""
Re-exporta el motor de categorías (`category_engine`).

Toda orquestación de listados, filtros, SEO y cards debe delegarse en `build_category_page`
y el registro `CATEGORY_CONTRACT_REGISTRY`; no duplicar lógica en vistas ni servicios.
"""

from .category_contract import CategoryContractSpec
from .category_engine import (
    CATEGORY_CONTRACT_REGISTRY,
    CategoryHeroContext,
    CategoryPageContext,
    CategoryPagination,
    CategorySeoBundle,
    LOCATION_LANDING_CONFIG,
    apply_category_filters,
    apply_category_search,
    apply_search,
    build_browse_listings_queryset,
    build_category_page,
    build_category_seo,
    build_category_seo_context,
    build_seo,
    enrich_category_scoped_listing_queryset,
    get_category_behavior,
    get_category_behavior_spec,
    get_category_contract,
)
from .category_engine_queryplan import (
    QueryPlan,
    apply_query_plan,
    browse_listings_query_plan,
    merge_query_plans,
)
from .listing_sort import apply_listing_order, parse_sort_param
from .services_promotions import (
    annotate_listing_promotions,
    create_listing_promotion,
    get_active_promotions_q,
)

CategoryBehaviorSpec = CategoryContractSpec

__all__ = [
    "annotate_listing_promotions",
    "create_listing_promotion",
    "get_active_promotions_q",
    "apply_listing_order",
    "parse_sort_param",
    "CATEGORY_CONTRACT_REGISTRY",
    "CategoryBehaviorSpec",
    "CategoryContractSpec",
    "CategoryHeroContext",
    "CategoryPageContext",
    "CategoryPagination",
    "CategorySeoBundle",
    "LOCATION_LANDING_CONFIG",
    "QueryPlan",
    "apply_category_filters",
    "apply_category_search",
    "apply_query_plan",
    "apply_search",
    "browse_listings_query_plan",
    "build_browse_listings_queryset",
    "build_category_page",
    "build_category_seo",
    "build_category_seo_context",
    "build_seo",
    "enrich_category_scoped_listing_queryset",
    "get_category_behavior",
    "get_category_behavior_spec",
    "get_category_contract",
    "merge_query_plans",
]
