"""Consultas reutilizables sobre categorías (fuente única para home, publicar, footer)."""

from __future__ import annotations

from django.db.models import Count, Q

from apps.listings.models import Listing

from .models import Category


def root_categories():
    """Categorías de primer nivel, ordenadas para UI."""
    return Category.objects.filter(parent__isnull=True).order_by("order", "name")


def root_categories_for_homepage_annotated(limit: int = 6):
    """
    Categorías raíz con conteo de anuncios publicados (para home y buscador).
    """
    return (
        Category.objects.filter(parent__isnull=True)
        .annotate(
            published_count=Count(
                "listings",
                filter=Q(
                    listings__status=Listing.Status.PUBLISHED,
                ),
            )
        )
        .order_by("order", "name")[: max(1, limit)]
    )


def preferred_explore_category() -> Category | None:
    """Categoría raíz con más anuncios publicados (CTA explorar)."""
    return (
        Category.objects.filter(parent__isnull=True)
        .annotate(
            _pub_count=Count(
                "listings",
                filter=Q(
                    listings__status=Listing.Status.PUBLISHED,
                ),
            )
        )
        .order_by("-_pub_count", "order", "name")
        .first()
    )
