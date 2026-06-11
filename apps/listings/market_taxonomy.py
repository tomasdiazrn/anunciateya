from __future__ import annotations

from django.db.models import QuerySet

from .models import MarketBrand, MarketModel


FALLBACK_BRAND_NAME = "Otra marca"
FALLBACK_MODEL_NAME = "Otro"


def _item_type_value(item_type: str | None) -> str:
    return (item_type or "").strip()


def market_brand_queryset(
    category_slug: str,
    *,
    item_type: str | None = None,
) -> QuerySet[MarketBrand]:
    qs = MarketBrand.objects.filter(
        is_active=True,
        models__category_slug=category_slug,
        models__is_active=True,
    )
    item_type_value = _item_type_value(item_type)
    if item_type_value:
        qs = qs.filter(models__item_type=item_type_value)
    return qs.distinct().order_by("name")


def market_model_queryset(
    category_slug: str,
    brand_id: int | None,
    *,
    item_type: str | None = None,
) -> QuerySet[MarketModel]:
    if not brand_id:
        return MarketModel.objects.none()
    qs = MarketModel.objects.filter(
        is_active=True,
        brand__is_active=True,
        brand_id=brand_id,
        category_slug=category_slug,
    )
    item_type_value = _item_type_value(item_type)
    if item_type_value:
        qs = qs.filter(item_type=item_type_value)
    return qs.select_related("brand").order_by("sort_order", "name")


def market_model_belongs_to_brand(
    category_slug: str,
    brand: MarketBrand | None,
    model: MarketModel | None,
    *,
    item_type: str | None = None,
) -> bool:
    if not brand or not model:
        return False
    qs = market_model_queryset(
        category_slug,
        brand.pk,
        item_type=item_type,
    )
    return qs.filter(pk=model.pk).exists()


def scoped_brand_id_from_request_value(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
