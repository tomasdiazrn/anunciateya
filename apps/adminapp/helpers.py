"""Admin query helpers."""

from django.db.models import Q


def listing_search_q(value: str) -> Q:
    """Search listings by title, description, location (case-insensitive)."""
    if not (value or "").strip():
        return Q()
    q = value.strip()
    return (
        Q(title__icontains=q)
        | Q(description__icontains=q)
        | Q(location__icontains=q)
    )

