import re

from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """Lookup dict in templates: {{ seller_verification_map|dict_get:listing.seller_id }}"""
    if mapping is None:
        return None
    if key is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def seq_get(seq, idx):
    """Index lists/tuples safely in templates: {{ seq|seq_get:forloop.counter0 }}"""
    if seq is None:
        return None
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    try:
        return seq[i]
    except Exception:
        return None


_RE_TRAILING_INTERNAL_ID = re.compile(r"\s+#\d+\s*$")
_RE_TRAILING_YEAR = re.compile(r"\s+(19\d{2}|20\d{2})\s*$")
_RE_MONEY_DECIMALS = re.compile(r"([.,]00)\s*$")


@register.filter
def card_title_clean(title: str) -> str:
    """
    UI title for listing cards:
    - strip internal trailing "#123"
    - strip trailing 4-digit year (auto-style), keeping brand + model
    """
    t = (title or "").strip()
    t = _RE_TRAILING_INTERNAL_ID.sub("", t).strip()
    t = _RE_TRAILING_YEAR.sub("", t).strip()
    return t


@register.filter
def card_specs_for_title(attributes, title: str):
    """
    Remove duplicated "brand model" from attributes when it matches the title.
    Keeps year/km/transmission in a single-line specs list.
    """
    attrs = list(attributes or [])
    if not attrs:
        return []
    t = card_title_clean(title)
    head = (attrs[0] or "").strip()
    if head and t and head.lower() in t.lower():
        attrs = attrs[1:]
    return attrs


@register.filter
def price_no_decimals(price_display: str) -> str:
    """
    Presentación UI: oculta decimales .00/,00 sin tocar el valor backend.
    Ej: "$15,047.00" -> "$15,047"
    """
    s = (price_display or "").strip()
    return _RE_MONEY_DECIMALS.sub("", s)


@register.filter
def field_maxlength(bound_field):
    """
    Límite de caracteres para UI (contador): widget.attrs.maxlength o field.max_length.
    None si no hay límite conocido (p. ej. TextField sin max_length en el modelo).
    """
    if bound_field is None:
        return None
    try:
        field = bound_field.field
        w = field.widget.attrs.get("maxlength")
        if w is not None and w != "":
            return int(w)
        ml = getattr(field, "max_length", None)
        if ml is not None:
            return int(ml)
    except (TypeError, ValueError, AttributeError):
        return None
    return None
