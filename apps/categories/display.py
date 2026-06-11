"""Metadatos de UI para categorías raíz (icono Font Awesome y orden en home/publicar)."""

from __future__ import annotations

ROOT_CATEGORY_DISPLAY: dict[str, dict[str, str | int]] = {
    "autos": {"icon": "fa-solid fa-car-side", "order": 1},
    "inmuebles": {"icon": "fa-solid fa-house", "order": 2},
    "electronica": {"icon": "fa-solid fa-mobile-screen-button", "order": 3},
    "motos": {"icon": "fa-solid fa-motorcycle", "order": 4},
    "hogar": {"icon": "fa-solid fa-couch", "order": 5},
    "instrumentos": {"icon": "fa-solid fa-guitar", "order": 6},
}


def apply_root_category_display(category, *, save: bool = True) -> list[str]:
    """Aplica icono y orden conocidos por slug. Devuelve campos actualizados."""
    meta = ROOT_CATEGORY_DISPLAY.get((category.slug or "").lower())
    if not meta:
        if category.order == 0:
            category.order = 50
            if save:
                category.save(update_fields=["order"])
            return ["order"]
        return []

    updates: list[str] = []
    if category.icon != meta["icon"]:
        category.icon = str(meta["icon"])
        updates.append("icon")
    if category.order != meta["order"]:
        category.order = int(meta["order"])
        updates.append("order")
    if updates and save:
        category.save(update_fields=updates)
    return updates
