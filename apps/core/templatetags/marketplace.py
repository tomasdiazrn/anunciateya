from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """Lookup dict in templates: {{ trust_map|dict_get:listing.seller_id }}"""
    if mapping is None:
        return None
    if key is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
