from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.listings.category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    VEHICLE_SLUG,
)
from apps.listings.electronics_market import ELECTRONICS_TYPE_MARKET_TAXONOMY
from apps.listings.homegoods_market import HOMEGOODS_TYPE_MARKET_TAXONOMY
from apps.listings.market_taxonomy import FALLBACK_MODEL_NAME
from apps.listings.models import MarketBrand, MarketModel
from apps.listings.motorcycle_market import MOTORCYCLE_MARKET_TAXONOMY
from apps.listings.vehicle_market import vehicle_market_taxonomy_with_fallback


def _unique_slug(model, value: str) -> str:
    base = slugify(value)[:80] or "opcion"
    candidate = base
    n = 0
    while model.objects.filter(slug=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _item_type_value(item_type) -> str:
    return str(getattr(item_type, "value", item_type) or "").strip()


def _get_brand(name: str) -> tuple[MarketBrand, bool]:
    normalized = (name or "").strip()
    brand = MarketBrand.objects.filter(name__iexact=normalized).first()
    if brand:
        if not brand.is_active:
            brand.is_active = True
            brand.save(update_fields=["is_active"])
        return brand, False
    return (
        MarketBrand.objects.create(
            name=normalized,
            slug=_unique_slug(MarketBrand, normalized),
            is_active=True,
        ),
        True,
    )


def _sync_model(
    *,
    brand: MarketBrand,
    category_slug: str,
    item_type: str,
    name: str,
    sort_order: int,
) -> bool:
    normalized = (name or "").strip()
    model = MarketModel.objects.filter(
        brand=brand,
        category_slug=category_slug,
        item_type=item_type,
        name__iexact=normalized,
    ).first()
    if model:
        updates: list[str] = []
        if not model.is_active:
            model.is_active = True
            updates.append("is_active")
        if model.sort_order != sort_order:
            model.sort_order = sort_order
            updates.append("sort_order")
        if updates:
            model.save(update_fields=updates)
        return False
    MarketModel.objects.create(
        brand=brand,
        category_slug=category_slug,
        item_type=item_type,
        name=normalized,
        slug=slugify(normalized)[:80] or "modelo",
        is_active=True,
        sort_order=sort_order,
    )
    return True


def _sync_flat_taxonomy(category_slug: str, taxonomy: dict[str, list[str]]) -> tuple[int, int]:
    created_brands = 0
    created_models = 0
    for brand_name, models in taxonomy.items():
        brand, brand_created = _get_brand(brand_name)
        created_brands += int(brand_created)
        for idx, model_name in enumerate(models, start=1):
            created_models += int(
                _sync_model(
                    brand=brand,
                    category_slug=category_slug,
                    item_type="",
                    name=model_name,
                    sort_order=idx,
                )
            )
    return created_brands, created_models


def _sync_type_taxonomy(
    category_slug: str,
    taxonomy_by_type: dict[object, dict[str, list[str]]],
) -> tuple[int, int]:
    created_brands = 0
    created_models = 0
    for item_type, taxonomy in taxonomy_by_type.items():
        item_type_value = _item_type_value(item_type)
        for brand_name, models in taxonomy.items():
            brand, brand_created = _get_brand(brand_name)
            created_brands += int(brand_created)
            for idx, model_name in enumerate(
                list(dict.fromkeys([*models, FALLBACK_MODEL_NAME])),
                start=1,
            ):
                created_models += int(
                    _sync_model(
                        brand=brand,
                        category_slug=category_slug,
                        item_type=item_type_value,
                        name=model_name,
                        sort_order=idx if model_name != FALLBACK_MODEL_NAME else 999,
                    )
                )
    return created_brands, created_models


class Command(BaseCommand):
    help = "Sincroniza marcas/modelos curados para autos, motos, electrónica y hogar."

    @transaction.atomic
    def handle(self, *args, **options):
        vehicle_brands, vehicle_models = _sync_flat_taxonomy(
            VEHICLE_SLUG,
            vehicle_market_taxonomy_with_fallback(),
        )
        motorcycle_brands, motorcycle_models = _sync_flat_taxonomy(
            MOTORCYCLE_SLUG,
            {
                brand: list(dict.fromkeys([*models, FALLBACK_MODEL_NAME]))
                for brand, models in MOTORCYCLE_MARKET_TAXONOMY.items()
            },
        )
        electronics_brands, electronics_models = _sync_type_taxonomy(
            ELECTRONICS_SLUG,
            ELECTRONICS_TYPE_MARKET_TAXONOMY,
        )
        home_brands, home_models = _sync_type_taxonomy(
            HOMEGOODS_SLUG,
            HOMEGOODS_TYPE_MARKET_TAXONOMY,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Taxonomía sincronizada: "
                f"autos {vehicle_brands}/{vehicle_models}, "
                f"motos {motorcycle_brands}/{motorcycle_models}, "
                f"electrónica {electronics_brands}/{electronics_models}, "
                f"hogar {home_brands}/{home_models} "
                "(marcas/modelos nuevos)."
            )
        )
