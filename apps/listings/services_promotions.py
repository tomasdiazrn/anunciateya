"""
Promociones de listados (destacado / impulso): ventanas temporales, listo para Stripe.

Las reglas activas se resuelven por fechas en SQL (`Now()`), sin cron ni escrituras en Listing.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import (
    Case,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.functions import Now
from django.utils import timezone

from .models import Listing, ListingPromotion


def get_active_promotions_q(*, prefix: str = "promotions") -> Q:
    """Q reutilizable: ventana activa (útil en filtros / agregados)."""
    now = timezone.now()
    return Q(
        **{
            f"{prefix}__is_active": True,
            f"{prefix}__starts_at__lte": now,
            f"{prefix}__ends_at__gte": now,
        }
    )


def _exists_active(
    *,
    promotion_type: str,
) -> Exists:
    return Exists(
        ListingPromotion.objects.filter(
            listing_id=OuterRef("pk"),
            type=promotion_type,
            is_active=True,
            starts_at__lte=Now(),
            ends_at__gte=Now(),
        )
    )


def listing_list_base_annotations() -> dict[str, Any]:
    """
    Annotations del listado público: promociones activas + is_featured combinado (promo o legacy).

    Usa `Now()` para que la ventana se evalúe al ejecutar la query (no al importar módulo).
    """
    ex_f = _exists_active(promotion_type=ListingPromotion.PromotionType.FEATURED)
    ex_b = _exists_active(promotion_type=ListingPromotion.PromotionType.BOOST)
    return {
        "has_active_featured": Case(
            When(ex_f, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        "has_active_boost": Case(
            When(ex_b, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        "is_featured": Case(
            When(ex_f, then=Value(1)),
            When(featured_until__gt=Now(), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    }


def annotate_listing_promotions(qs: QuerySet) -> QuerySet:
    """Solo flags de promoción (Exists); combinable con otras annotations."""
    ann = listing_list_base_annotations()
    return qs.annotate(
        has_active_featured=ann["has_active_featured"],
        has_active_boost=ann["has_active_boost"],
    )


def create_listing_promotion(
    listing: Listing,
    user: Any,
    promotion_type: str,
    duration_days: int,
    *,
    external_payment_id: str = "",
) -> ListingPromotion:
    """
    Crea una promoción en ventana [now, now+duration).

    `external_payment_id` queda listo para webhooks Stripe sin acoplar aquí el SDK.
    """
    if duration_days < 1:
        raise ValueError("duration_days debe ser >= 1")
    if promotion_type not in ListingPromotion.PromotionType:
        raise ValueError("type inválido")
    now = timezone.now()
    return ListingPromotion.objects.create(
        listing=listing,
        user=user,
        type=promotion_type,
        starts_at=now,
        ends_at=now + timedelta(days=int(duration_days)),
        is_active=True,
        external_payment_id=(external_payment_id or "")[:255],
    )
