"""Validación y metadatos de geocodificación para ubicación de inmuebles."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

ECUADOR_BBOX = {
    "min_lng": Decimal("-92.008"),
    "min_lat": Decimal("-5.015"),
    "max_lng": Decimal("-75.233"),
    "max_lat": Decimal("1.442"),
}

MAPBOX_PROVIDER = "mapbox"


def coordinates_within_ecuador(latitude: Decimal, longitude: Decimal) -> bool:
    return (
        ECUADOR_BBOX["min_lat"] <= latitude <= ECUADOR_BBOX["max_lat"]
        and ECUADOR_BBOX["min_lng"] <= longitude <= ECUADOR_BBOX["max_lng"]
    )


def ecuador_bbox_querystring() -> str:
    """BBox Mapbox: minLng,minLat,maxLng,maxLat."""
    b = ECUADOR_BBOX
    return f"{b['min_lng']},{b['min_lat']},{b['max_lng']},{b['max_lat']}"


def apply_mapbox_geocoding_metadata(prop, *, provider: str, place_id: str) -> None:
    """Persiste metadatos cuando las coordenadas provienen de Mapbox."""
    prop.geocoding_provider = (provider or "").strip()
    prop.geocoding_place_id = (place_id or "").strip()
    if prop.geocoding_provider == MAPBOX_PROVIDER and prop.has_coordinates:
        prop.geocoded_at = timezone.now()
    elif not prop.has_coordinates:
        prop.geocoding_provider = ""
        prop.geocoding_place_id = ""
        prop.geocoded_at = None


def clear_property_geocoding(prop) -> None:
    from .models import PropertyListing

    prop.address_line = ""
    prop.address_place_label = ""
    prop.latitude = None
    prop.longitude = None
    prop.location_precision = PropertyListing.LocationPrecision.SECTOR
    prop.geocoding_provider = ""
    prop.geocoding_place_id = ""
    prop.geocoded_at = None
