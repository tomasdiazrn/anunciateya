"""SEO centralizado por categoría (hub, browse, location). Usado solo vía category_engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from django.http import HttpRequest
from django.urls import reverse

from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .services import (
    ELECTRONICS_HUB_DEFAULT_META_TITLE_CORE,
    HOME_HUB_DEFAULT_META_TITLE_CORE,
    MOTORCYCLE_HUB_DEFAULT_META_TITLE_CORE,
    build_autos_browse_heading,
    build_autos_meta_description,
    build_category_hero,
    build_electronics_browse_heading,
    build_electronics_hub_default_meta_description,
    build_electronics_meta_description,
    build_home_browse_heading,
    build_home_hub_default_meta_description,
    build_home_meta_description,
    build_motorcycle_browse_heading,
    build_motorcycle_hub_default_meta_description,
    build_motorcycle_meta_description,
    build_property_browse_heading,
    build_property_meta_description,
    electronics_hub_uses_default_meta_title,
    home_hub_uses_default_meta_title,
    motorcycle_hub_uses_default_meta_title,
    vehicle_filter_marca_model_labels,
)


def _category_intro_text(category_name: str, city: str) -> str:
    return (
        f"Encuentra {category_name.lower()} en venta en {city} de forma segura. "
        f"Contacta vendedores verificados y evita estafas."
    )


@dataclass
class CategorySeoBundle:
    meta_title: str
    meta_description: str
    canonical_href: str | None
    hero_title: str
    hero_subtitle: str
    list_heading: str
    list_subtitle: str
    browse_h1: str
    page_header_title_tag: str
    show_category_hero: bool
    dynamic_list_heading: str | None


def _location_canonical_autos(request: HttpRequest, location_slug: str) -> str | None:
    if location_slug == "guayaquil":
        return request.build_absolute_uri(
            reverse(
                "location_guayaquil_category",
                kwargs={"category_slug": VEHICLE_SLUG},
            )
        )
    if location_slug == "samborondon":
        return request.build_absolute_uri(
            reverse(
                "location_samborondon_category",
                kwargs={"category_slug": VEHICLE_SLUG},
            )
        )
    return None


def _location_canonical_electronics(request: HttpRequest, location_slug: str) -> str | None:
    if location_slug == "guayaquil":
        return request.build_absolute_uri(
            reverse(
                "location_guayaquil_category",
                kwargs={"category_slug": ELECTRONICS_SLUG},
            )
        )
    if location_slug == "samborondon":
        return request.build_absolute_uri(
            reverse(
                "location_samborondon_category",
                kwargs={"category_slug": ELECTRONICS_SLUG},
            )
        )
    return None


def _location_canonical_home(request: HttpRequest, location_slug: str) -> str | None:
    if location_slug == "guayaquil":
        return request.build_absolute_uri(
            reverse(
                "location_guayaquil_category",
                kwargs={"category_slug": HOMEGOODS_SLUG},
            )
        )
    if location_slug == "samborondon":
        return request.build_absolute_uri(
            reverse(
                "location_samborondon_category",
                kwargs={"category_slug": HOMEGOODS_SLUG},
            )
        )
    return None


def _location_canonical_property(request: HttpRequest, location_slug: str) -> str | None:
    if location_slug == "guayaquil":
        return request.build_absolute_uri(
            reverse(
                "location_guayaquil_category",
                kwargs={"category_slug": PROPERTY_SLUG},
            )
        )
    if location_slug == "samborondon":
        return request.build_absolute_uri(
            reverse(
                "location_samborondon_category",
                kwargs={"category_slug": PROPERTY_SLUG},
            )
        )
    return None


def seo_vehicle(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    frame = ctx["frame"]
    brand = ctx["brand"]
    city = ctx["city"]
    category = ctx["category"]
    parsed = ctx["parsed"]
    result_count = ctx["result_count"]
    q_raw = ctx.get("q_raw") or ""
    location_display = ctx.get("location_display")
    location_slug = ctx.get("location_slug") or ""
    filters_active = ctx["filters_active"]

    brand_name, model_name = vehicle_filter_marca_model_labels(parsed)
    dynamic_list_heading = build_autos_browse_heading(
        city=city,
        location_display=location_display,
        parsed=parsed,
        brand_name=brand_name,
        model_name=model_name,
    )
    list_subtitle_browse = (
        "Filtrá por marca, modelo, año, precio y transmisión. "
        "Revisa confianza del vendedor antes de contactar."
    )
    list_subtitle_loc = (
        f"Filtrá autos en {location_display} por marca, año, precio y transmisión. "
        "Revisa confianza del vendedor antes de contactar."
    )

    if frame == "browse":
        meta_title = f"{dynamic_list_heading} | {brand}"
        meta_description = build_autos_meta_description(
            city=city,
            heading_hint=dynamic_list_heading,
            result_count=result_count,
        )
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": VEHICLE_SLUG})
        )
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=place,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    if frame == "hub":
        meta_title = f"{dynamic_list_heading} | {brand}"
        meta_description = build_autos_meta_description(
            city=city,
            heading_hint=dynamic_list_heading,
            result_count=result_count,
        )
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": VEHICLE_SLUG})
        )
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=city,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    # location_hub
    meta_title = f"{dynamic_list_heading} | {brand}"
    meta_description = build_autos_meta_description(
        city=location_display or city,
        heading_hint=dynamic_list_heading,
        result_count=result_count,
    )
    canonical = _location_canonical_autos(request, location_slug)
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=location_display or city,
        filters_active=filters_active,
        filtered_heading=dynamic_list_heading if filters_active else None,
    )
    return CategorySeoBundle(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_href=canonical,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=dynamic_list_heading,
        list_subtitle=list_subtitle_loc,
        browse_h1=dynamic_list_heading,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=dynamic_list_heading,
    )


def seo_property(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    frame = ctx["frame"]
    brand = ctx["brand"]
    city = ctx["city"]
    category = ctx["category"]
    parsed = ctx["parsed"]
    result_count = ctx["result_count"]
    q_raw = ctx.get("q_raw") or ""
    location_display = ctx.get("location_display")
    location_slug = ctx.get("location_slug") or ""
    filters_active = ctx["filters_active"]

    dynamic_list_heading = build_property_browse_heading(
        city=city,
        location_display=location_display,
        parsed=parsed,
    )
    list_subtitle_browse = (
        "Filtrá por tipo, operación, habitaciones y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )
    list_subtitle_loc = (
        f"Filtrá inmuebles en {location_display} por tipo, operación, habitaciones y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )

    if frame == "browse":
        meta_title = f"{dynamic_list_heading} | {brand}"
        meta_description = build_property_meta_description(
            city=location_display or city,
            heading_hint=dynamic_list_heading,
            result_count=result_count,
        )
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": PROPERTY_SLUG})
        )
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=place,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    if frame == "hub":
        meta_title = f"{dynamic_list_heading} | {brand}"
        meta_description = build_property_meta_description(
            city=city,
            heading_hint=dynamic_list_heading,
            result_count=result_count,
        )
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": PROPERTY_SLUG})
        )
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=city,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    meta_title = f"{dynamic_list_heading} | {brand}"
    meta_description = build_property_meta_description(
        city=location_display or city,
        heading_hint=dynamic_list_heading,
        result_count=result_count,
    )
    canonical = _location_canonical_property(request, location_slug)
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=location_display or city,
        filters_active=filters_active,
        filtered_heading=dynamic_list_heading if filters_active else None,
    )
    return CategorySeoBundle(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_href=canonical,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=dynamic_list_heading,
        list_subtitle=list_subtitle_loc,
        browse_h1=dynamic_list_heading,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=dynamic_list_heading,
    )


def seo_electronics(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    frame = ctx["frame"]
    brand = ctx["brand"]
    city = ctx["city"]
    category = ctx["category"]
    parsed = ctx["parsed"]
    result_count = ctx["result_count"]
    q_raw = ctx.get("q_raw") or ""
    location_display = ctx.get("location_display")
    location_slug = ctx.get("location_slug") or ""
    filters_active = ctx["filters_active"]

    dynamic_list_heading = build_electronics_browse_heading(
        city=city,
        location_display=location_display,
        parsed=parsed,
    )
    list_subtitle_browse = (
        "Filtrá por marca, condición, garantía y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )
    list_subtitle_loc = (
        f"Filtrá electrónica en {location_display} por marca, condición, garantía y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )

    def _meta_pair() -> tuple[str, str]:
        if electronics_hub_uses_default_meta_title(q_raw=q_raw, parsed=parsed):
            return (
                f"{ELECTRONICS_HUB_DEFAULT_META_TITLE_CORE} | {brand}",
                build_electronics_hub_default_meta_description(
                    city=location_display or city,
                    result_count=result_count,
                ),
            )
        return (
            f"{dynamic_list_heading} | {brand}",
            build_electronics_meta_description(
                city=location_display or city,
                heading_hint=dynamic_list_heading,
                result_count=result_count,
            ),
        )

    if frame == "browse":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": ELECTRONICS_SLUG})
        )
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=place,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    if frame == "hub":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": ELECTRONICS_SLUG})
        )
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=city,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    meta_title, meta_description = _meta_pair()
    canonical = _location_canonical_electronics(request, location_slug)
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=location_display or city,
        filters_active=filters_active,
        filtered_heading=dynamic_list_heading if filters_active else None,
    )
    return CategorySeoBundle(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_href=canonical,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=dynamic_list_heading,
        list_subtitle=list_subtitle_loc,
        browse_h1=dynamic_list_heading,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=dynamic_list_heading,
    )


def seo_home(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    frame = ctx["frame"]
    brand = ctx["brand"]
    city = ctx["city"]
    category = ctx["category"]
    parsed = ctx["parsed"]
    result_count = ctx["result_count"]
    q_raw = ctx.get("q_raw") or ""
    location_display = ctx.get("location_display")
    location_slug = ctx.get("location_slug") or ""
    filters_active = ctx["filters_active"]

    dynamic_list_heading = build_home_browse_heading(
        city=city,
        location_display=location_display,
        parsed=parsed,
    )
    list_subtitle_browse = (
        "Filtrá por tipo de artículo, condición y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )
    list_subtitle_loc = (
        f"Filtrá hogar en {location_display} por tipo, condición y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )

    def _meta_pair() -> tuple[str, str]:
        if home_hub_uses_default_meta_title(q_raw=q_raw, parsed=parsed):
            return (
                f"{HOME_HUB_DEFAULT_META_TITLE_CORE} | {brand}",
                build_home_hub_default_meta_description(
                    city=location_display or city,
                    result_count=result_count,
                ),
            )
        return (
            f"{dynamic_list_heading} | {brand}",
            build_home_meta_description(
                city=location_display or city,
                heading_hint=dynamic_list_heading,
                result_count=result_count,
            ),
        )

    if frame == "browse":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": HOMEGOODS_SLUG})
        )
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=place,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    if frame == "hub":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": HOMEGOODS_SLUG})
        )
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=city,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    meta_title, meta_description = _meta_pair()
    canonical = _location_canonical_home(request, location_slug)
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=location_display or city,
        filters_active=filters_active,
        filtered_heading=dynamic_list_heading if filters_active else None,
    )
    return CategorySeoBundle(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_href=canonical,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=dynamic_list_heading,
        list_subtitle=list_subtitle_loc,
        browse_h1=dynamic_list_heading,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=dynamic_list_heading,
    )


def seo_motorcycle(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    frame = ctx["frame"]
    brand = ctx["brand"]
    city = ctx["city"]
    category = ctx["category"]
    parsed = ctx["parsed"]
    result_count = ctx["result_count"]
    q_raw = ctx.get("q_raw") or ""
    location_display = ctx.get("location_display")
    location_slug = ctx.get("location_slug") or ""
    filters_active = ctx["filters_active"]

    dynamic_list_heading = build_motorcycle_browse_heading(
        city=city,
        location_display=location_display,
        parsed=parsed,
    )
    list_subtitle_browse = (
        "Filtrá por marca, modelo, año, cilindrada, combustible y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )
    list_subtitle_loc = (
        f"Filtrá motos en {location_display} por marca, año, cilindrada, combustible y precio. "
        "Revisa confianza del vendedor antes de contactar."
    )

    def _meta_pair() -> tuple[str, str]:
        if motorcycle_hub_uses_default_meta_title(q_raw=q_raw, parsed=parsed):
            return (
                f"{MOTORCYCLE_HUB_DEFAULT_META_TITLE_CORE} | {brand}",
                build_motorcycle_hub_default_meta_description(
                    city=location_display or city,
                    result_count=result_count,
                ),
            )
        return (
            f"{dynamic_list_heading} | {brand}",
            build_motorcycle_meta_description(
                city=location_display or city,
                heading_hint=dynamic_list_heading,
                result_count=result_count,
            ),
        )

    if frame == "browse":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": MOTORCYCLE_SLUG})
        )
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=place,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    if frame == "hub":
        meta_title, meta_description = _meta_pair()
        canonical = request.build_absolute_uri(
            reverse("category_landing", kwargs={"slug": MOTORCYCLE_SLUG})
        )
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category.slug,
            category_name=category.name,
            place=city,
            filters_active=filters_active,
            filtered_heading=dynamic_list_heading if filters_active else None,
        )
        return CategorySeoBundle(
            meta_title=meta_title,
            meta_description=meta_description,
            canonical_href=canonical,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=dynamic_list_heading,
            list_subtitle=list_subtitle_browse,
            browse_h1=dynamic_list_heading,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=dynamic_list_heading,
        )

    meta_title, meta_description = _meta_pair()
    canonical = request.build_absolute_uri(
        reverse("category_landing", kwargs={"slug": MOTORCYCLE_SLUG})
    )
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=location_display or city,
        filters_active=filters_active,
        filtered_heading=dynamic_list_heading if filters_active else None,
    )
    return CategorySeoBundle(
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_href=canonical,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=dynamic_list_heading,
        list_subtitle=list_subtitle_loc,
        browse_h1=dynamic_list_heading,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=dynamic_list_heading,
    )


def seo_simple_category(request: HttpRequest, qs, ctx: dict[str, Any]) -> CategorySeoBundle:
    """Hub / ciudad sin filtros extendidos (electrónica, hogar, …)."""
    city = ctx["city"]
    brand = ctx["brand"]
    category = ctx["category"]
    place = ctx.get("location_display") or city
    intro = _category_intro_text(category.name, place)
    browse_h1 = f"{category.name} en {place}"
    hero_title, hero_subtitle = build_category_hero(
        category_slug=category.slug,
        category_name=category.name,
        place=place,
        filters_active=False,
        filtered_heading=None,
    )
    return CategorySeoBundle(
        meta_title=f"{category.name} en {place} | {brand}",
        meta_description=intro,
        canonical_href=None,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        list_heading=browse_h1,
        list_subtitle=intro,
        browse_h1=browse_h1,
        page_header_title_tag="h2",
        show_category_hero=True,
        dynamic_list_heading=None,
    )


def seo_location_market(
    *,
    display: str,
    city: str,
    brand: str,
) -> CategorySeoBundle:
    """Landing solo por ciudad (/guayaquil/, etc.): títulos y meta city-aware."""
    intro = (
        f"Explora anuncios clasificados en {display} y alrededores. "
        "Revisa la confianza del vendedor y no envíes dinero por adelantado sin respaldo."
    )
    browse_h1 = f"Anuncios en {display}"
    return CategorySeoBundle(
        meta_title=f"Anuncios en {display} y {city} | {brand}",
        meta_description=intro,
        canonical_href=None,
        hero_title="",
        hero_subtitle="",
        list_heading=browse_h1,
        list_subtitle=intro,
        browse_h1=browse_h1,
        page_header_title_tag="h1",
        show_category_hero=False,
        dynamic_list_heading=None,
    )


def seo_browse_generic(
    request: HttpRequest,
    qs,
    ctx: dict[str, Any],
) -> CategorySeoBundle:
    """/anuncios/ sin categoría extendida o sin category=."""
    brand = ctx["brand"]
    city = ctx["city"]
    category_obj = ctx.get("category_obj")
    category_slug = (ctx.get("category_slug") or "").strip()
    result_count = ctx["result_count"]
    location_display = ctx.get("location_display")

    if category_obj and category_slug and category_slug not in (
        VEHICLE_SLUG,
        PROPERTY_SLUG,
        MOTORCYCLE_SLUG,
        ELECTRONICS_SLUG,
        HOMEGOODS_SLUG,
    ):
        place = location_display or city
        hero_title, hero_subtitle = build_category_hero(
            category_slug=category_obj.slug,
            category_name=category_obj.name,
            place=place,
            filters_active=False,
            filtered_heading=None,
        )
        return CategorySeoBundle(
            meta_title=f"{hero_title} | {brand}",
            meta_description=(
                f"{hero_title}. Explora anuncios en {location_display or city} "
                "con señales de confianza."
            ),
            canonical_href=None,
            hero_title=hero_title,
            hero_subtitle=hero_subtitle,
            list_heading=hero_title,
            list_subtitle=(
                "Explora publicaciones en tu ciudad. Revisa confianza del vendedor "
                "y contacta por mensaje seguro."
            ),
            browse_h1=hero_title,
            page_header_title_tag="h2",
            show_category_hero=True,
            dynamic_list_heading=None,
        )

    return CategorySeoBundle(
        meta_title=f"Anuncios clasificados en {city} | {brand}",
        meta_description=(
            f"Explora anuncios locales en {city}: autos, inmuebles y más. "
            f"Contacta vendedores con señales de confianza y evita pagos adelantados sin respaldo."
        ),
        canonical_href=None,
        hero_title="",
        hero_subtitle="",
        list_heading="Anuncios",
        list_subtitle=(
            "Explora publicaciones en tu ciudad. Revisa confianza del vendedor "
            "y contacta por mensaje seguro."
        ),
        browse_h1="Anuncios",
        page_header_title_tag="h1",
        show_category_hero=False,
        dynamic_list_heading=None,
    )
