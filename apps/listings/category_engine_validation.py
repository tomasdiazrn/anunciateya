"""
Validación estricta del Category Engine al arranque (fail-fast, RuntimeError).

Complementa el contrato de registro: cada categoría debe exponer filtros, SEO, card DTO
y QueryPlan coherente para evitar N+1 y plantillas acopladas al ORM.
"""

from __future__ import annotations

from django.test import RequestFactory

from .category_engine_queryplan import QueryPlan, merge_query_plans, LISTING_LIST_BASE_PLAN
from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)

EXPECTED_CONTRACT_SLUGS = frozenset(
    {
        VEHICLE_SLUG,
        PROPERTY_SLUG,
        MOTORCYCLE_SLUG,
        ELECTRONICS_SLUG,
        HOMEGOODS_SLUG,
    }
)

SUPPORTED_SEARCH_FIELDS_BY_SLUG: dict[str, frozenset[str]] = {
    VEHICLE_SLUG: frozenset({"title", "description", "vehicle"}),
    PROPERTY_SLUG: frozenset({"title", "description", "property"}),
    MOTORCYCLE_SLUG: frozenset({"title", "description", "motorcycle"}),
    ELECTRONICS_SLUG: frozenset({"title", "description", "electronics"}),
    HOMEGOODS_SLUG: frozenset({"title", "description", "homegoods"}),
}

_EXTENSION_REL_PREFIX: dict[str, str] = {
    VEHICLE_SLUG: "vehicle",
    PROPERTY_SLUG: "property",
    MOTORCYCLE_SLUG: "motorcycle",
    ELECTRONICS_SLUG: "electronics",
    HOMEGOODS_SLUG: "homegoods",
}


def _plan_select_paths_cover_extension(paths: frozenset[str], slug: str) -> bool:
    prefix = _EXTENSION_REL_PREFIX.get(slug)
    if not prefix:
        return True
    return any(p == prefix or p.startswith(f"{prefix}__") for p in paths)


def validate_category_engine_at_startup() -> None:
    from .category_engine import (
        BROWSE_FRAME_SEO_BUILDER,
        CATEGORY_CONTRACT_REGISTRY,
    )

    if not callable(BROWSE_FRAME_SEO_BUILDER):
        raise RuntimeError("category_engine.BROWSE_FRAME_SEO_BUILDER debe ser un callable.")

    reg_keys = frozenset(CATEGORY_CONTRACT_REGISTRY.keys())
    if reg_keys != EXPECTED_CONTRACT_SLUGS:
        raise RuntimeError(
            f"CATEGORY_CONTRACT_REGISTRY debe cubrir exactamente {sorted(EXPECTED_CONTRACT_SLUGS)}; "
            f"tiene {sorted(reg_keys)}.",
        )

    rf = RequestFactory()

    for slug, spec in CATEGORY_CONTRACT_REGISTRY.items():
        if spec.slug != slug:
            raise RuntimeError(f"Contract slug mismatch: key={slug!r} spec.slug={spec.slug!r}")

        if not hasattr(spec, "filter_get_keys"):
            raise RuntimeError(f"{slug}: falta filter_get_keys en el contrato.")
        if not isinstance(spec.filter_get_keys, tuple):
            raise RuntimeError(f"{slug}: filter_get_keys debe ser tuple, tiene {type(spec.filter_get_keys)!r}.")

        fp, fa = spec.filter_parser, spec.filter_applier
        if fp is not None and not callable(fp):
            raise RuntimeError(f"{slug}: filter_parser debe ser callable o None.")
        if fa is not None and not callable(fa):
            raise RuntimeError(f"{slug}: filter_applier debe ser callable o None.")

        if not callable(spec.seo_builder):
            raise RuntimeError(f"{slug}: seo_builder obligatorio y callable.")

        if not (spec.card_template or "").strip():
            raise RuntimeError(f"{slug}: card_template (card DTO) obligatorio.")

        if not callable(spec.query_plan_builder):
            raise RuntimeError(f"{slug}: query_plan_builder obligatorio y callable.")

        req = rf.get(f"/{slug}/")
        ext_plan = spec.query_plan_builder(req, {"scope": "hub", "category_slug": slug})
        if not isinstance(ext_plan, QueryPlan):
            raise RuntimeError(
                f"{slug}: query_plan_builder debe devolver QueryPlan, obtuvo {type(ext_plan)!r}.",
            )
        merged = merge_query_plans(LISTING_LIST_BASE_PLAN, ext_plan)
        if "is_featured" not in merged.annotations:
            raise RuntimeError(
                f"{slug}: QueryPlan tras merge debe incluir anotación is_featured; "
                f"annotations={sorted(merged.annotations)}.",
            )
        paths = frozenset(merged.select_related)
        if not _plan_select_paths_cover_extension(paths, slug):
            raise RuntimeError(
                f"{slug}: QueryPlan hub (tras merge con base) debe incluir relación "
                f"{_EXTENSION_REL_PREFIX[slug]!r}; select_related={sorted(paths)}.",
            )

        exp_search = SUPPORTED_SEARCH_FIELDS_BY_SLUG.get(slug)
        if exp_search is None:
            raise RuntimeError(f"{slug}: falta entrada en SUPPORTED_SEARCH_FIELDS_BY_SLUG.")
        if spec.supported_search_fields != exp_search:
            raise RuntimeError(
                f"{slug}: supported_search_fields debe ser {sorted(exp_search)}; "
                f"tiene {sorted(spec.supported_search_fields)}.",
            )

        if tuple(spec.filter_get_keys) != spec.required_filters:
            raise RuntimeError(
                f"{slug}: required_filters y filter_get_keys deben coincidir; "
                f"required_filters={spec.required_filters!r} filter_get_keys={spec.filter_get_keys!r}",
            )

        if spec.required_filters:
            if spec.filter_parser is None or spec.filter_applier is None:
                raise RuntimeError(
                    f"{slug}: con required_filters no vacío hacen falta filter_parser y filter_applier.",
                )
        elif spec.filter_parser is not None or spec.filter_applier is not None:
            raise RuntimeError(
                f"{slug}: sin required_filters, filter_parser y filter_applier deben ser None.",
            )
