from django.conf import settings

from apps.categories.services import root_categories


def _footer_social_links():
    """Enlaces con icono para el pie; solo entradas con URL configurada."""
    spec = (
        ("SOCIAL_INSTAGRAM_URL", "Instagram", "fa-brands fa-instagram"),
        ("SOCIAL_TIKTOK_URL", "TikTok", "fa-brands fa-tiktok"),
        ("SOCIAL_YOUTUBE_URL", "YouTube", "fa-brands fa-youtube"),
        ("SOCIAL_LINKEDIN_URL", "LinkedIn", "fa-brands fa-linkedin-in"),
    )
    out = []
    for setting_name, label, icon in spec:
        url = (getattr(settings, setting_name, "") or "").strip()
        if url:
            out.append({"url": url, "label": label, "icon": icon})
    return out


def _google_tag_manager_id_for_request(request) -> str:
    """GTM container id only when appropriate (not DEBUG, not staff admin URLs)."""
    raw = (getattr(settings, "GOOGLE_TAG_MANAGER_ID", "") or "").strip()
    if not raw:
        return ""
    if getattr(settings, "DEBUG", False):
        return ""
    path = getattr(request, "path", "") or ""
    if path == "/admin":
        return ""
    for prefix in getattr(settings, "GOOGLE_TAG_MANAGER_EXCLUDED_PATH_PREFIXES", ()):
        if prefix and path.startswith(prefix):
            return ""
    return raw


def _meta_pixel_id_for_request(request) -> str:
    """Meta Pixel id when appropriate (same path/DEBUG rules as GTM)."""
    raw = (getattr(settings, "META_PIXEL_ID", "") or "").strip()
    if not raw:
        return ""
    if getattr(settings, "DEBUG", False):
        return ""
    path = getattr(request, "path", "") or ""
    if path == "/admin":
        return ""
    for prefix in getattr(settings, "GOOGLE_TAG_MANAGER_EXCLUDED_PATH_PREFIXES", ()):
        if prefix and path.startswith(prefix):
            return ""
    return raw


def footer_nav_categories(request):
    """Enlaces de categorías en pie (misma fuente que el resto del sitio)."""
    return {
        "footer_nav_categories": root_categories()[:8],
    }


def site_metadata(request):
    """SEO y marca en todos los templates."""
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    return {
        "site_name": getattr(settings, "SITE_NAME", "anunciateya.com"),
        "site_url": site_url,
        "seo_brand_name": brand,
        "seo_market_city": city,
        "default_page_title": f"{brand} — Compra y vende seguro en tu ciudad",
        "seo_default_description": (
            f"Anuncios clasificados en {city} y Ecuador. Publica gratis, contacta vendedores "
            f"con señales de confianza y evita pagos por adelantado sin respaldo."
        ),
        "google_tag_manager_id": _google_tag_manager_id_for_request(request),
        "meta_pixel_id": _meta_pixel_id_for_request(request),
        "facebook_domain_verification": (
            getattr(settings, "FACEBOOK_DOMAIN_VERIFICATION", "") or ""
        ).strip(),
        "footer_social_links": _footer_social_links(),
    }
