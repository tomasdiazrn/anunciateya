"""
Demo temporal: reemplaza las fotos de anuncios por URLs públicas de picsum.photos
(sin API key ni paquetes extra). Activar con STOCK_DEMO_LISTING_PHOTOS en settings.

Cada anuncio obtiene 10 URLs distintas (semilla estable por pk + índice).
"""

from __future__ import annotations

from django.conf import settings

STOCK_DEMO_COUNT = 10
_STOCK_W = 800
_STOCK_H = 600


def use_stock_demo_photos() -> bool:
    return bool(getattr(settings, "STOCK_DEMO_LISTING_PHOTOS", False))


def stock_demo_gallery_urls(listing: object) -> tuple[str, ...]:
    pk = int(getattr(listing, "pk", None) or 0)
    return tuple(
        f"https://picsum.photos/seed/webmkt-{pk}-{i}/{_STOCK_W}/{_STOCK_H}"
        for i in range(STOCK_DEMO_COUNT)
    )
