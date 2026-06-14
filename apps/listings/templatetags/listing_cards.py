from django import template

from ..category_engine import resolve_listing_card_template_path
from ..listing_card_dto import build_card_context

register = template.Library()


@register.filter
def listing_card_template(listing):
    """Resuelve la plantilla DTO según contrato de categoría (compat)."""
    return resolve_listing_card_template_path(listing)


@register.inclusion_tag(
    "components/marketplace/listing_card_dto_resolve.html",
    takes_context=True,
)
def render_listing_card_from_dto(context, listing):
    """Card de listado 100 % DTO: sin acceso a extensiones ORM en plantillas."""
    seller_verification_map = context.get("seller_verification_map") or {}
    slug = listing.category.slug
    card = build_card_context(listing, slug, seller_verification_map=seller_verification_map)
    return {"card": card}
