from django.conf import settings

from apps.categories.services import root_categories


def _hosting_alert_context(request):
    """Hosting admin alerts are global, but only visible inside staff admin pages."""
    path = getattr(request, "path", "") or ""
    if not (path == "/admin" or path.startswith("/admin/")):
        return {}

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
        return {}

    from apps.adminapp.hosting import (  # Imported lazily to keep public context light.
        HOSTING_MEMBERSHIP_POPUP_DAYS,
        build_renewal_url,
        get_hosting_membership,
    )

    membership = get_hosting_membership()
    days_remaining = membership.days_remaining
    is_expiring = membership.is_expiring
    is_expired = membership.is_expired

    return {
        "ADMIN_HOSTING_MEMBERSHIP": membership,
        "ADMIN_HOSTING_RENEWAL_URL": build_renewal_url(request),
        "ADMIN_HOSTING_SHOW_ALERT": membership.show_alert,
        "ADMIN_HOSTING_SHOW_POPUP": (
            is_expired
            or (
                is_expiring
                and days_remaining is not None
                and 0 <= days_remaining <= HOSTING_MEMBERSHIP_POPUP_DAYS
            )
        ),
        "ADMIN_HOSTING_POPUP_BLOCKING": is_expired,
    }


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


def _analytics_surface_allowed(request) -> bool:
    """Misma superficie que GTM/Pixel: no DEBUG, no /admin, prefijos excluidos."""
    if getattr(settings, "DEBUG", False):
        return False
    path = getattr(request, "path", "") or ""
    if path == "/admin":
        return False
    for prefix in getattr(settings, "GOOGLE_TAG_MANAGER_EXCLUDED_PATH_PREFIXES", ()):
        if prefix and path.startswith(prefix):
            return False
    return True


def _marketing_tag_id_for_request(request, raw_id: str) -> str:
    """GTM / Meta: id solo si la petición está en superficie pública y el id está configurado."""
    raw = (raw_id or "").strip()
    if not raw:
        return ""
    if not _analytics_surface_allowed(request):
        return ""
    return raw


def _google_tag_manager_id_for_request(request) -> str:
    """GTM container id only when appropriate (not DEBUG, not staff admin URLs)."""
    return _marketing_tag_id_for_request(
        request, getattr(settings, "GOOGLE_TAG_MANAGER_ID", "") or ""
    )


def _meta_pixel_id_for_request(request) -> str:
    """Meta Pixel id when appropriate (same path/DEBUG rules as GTM)."""
    return _marketing_tag_id_for_request(
        request, getattr(settings, "META_PIXEL_ID", "") or ""
    )


def footer_nav_categories(request):
    """Enlaces de categorías en pie (misma fuente que el resto del sitio)."""
    return {
        "footer_nav_categories": root_categories()[:8],
    }


def _brand_font_stylesheet_url() -> str:
    """URL de fuente para la identidad visual pública."""
    display = getattr(settings, "BRAND_FONT_DISPLAY", "General Sans")
    body = getattr(settings, "BRAND_FONT_BODY", "General Sans")
    families = {display.strip(), body.strip()}
    if families == {"General Sans"}:
        return (
            "https://api.fontshare.com/v2/css?"
            "f[]=general-sans@400,500,600,700&display=swap"
        )

    display_param = display.replace(" ", "+")
    body_param = body.replace(" ", "+")
    return (
        "https://fonts.googleapis.com/css2?"
        f"family={body_param}:wght@400;500"
        f"&family={display_param}:wght@500;600;700"
        "&display=swap"
    )


def site_metadata(request):
    """SEO y marca en todos los templates."""
    site_domain = getattr(settings, "PUBLIC_SITE_DOMAIN", "anunciateya.com")
    site_url = getattr(settings, "PUBLIC_SITE_URL", "https://anunciateya.com").rstrip("/")
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    context = {
        "site_name": site_domain,
        "site_public_domain": site_domain,
        "site_url": site_url,
        "seo_brand_name": brand,
        "seo_market_city": city,
        "default_page_title": f"{brand} — Compra y vende seguro en tu ciudad",
        "seo_default_description": (
            f"Anuncios clasificados en {city} y Ecuador. Publica gratis, contacta vendedores "
            f"con señales de confianza y evita pagos por adelantado sin respaldo."
        ),
        "brand_logo": getattr(settings, "BRAND_LOGO_PATH", "img/AnunciateYa_Logo.png"),
        "brand_logo_white": getattr(
            settings, "BRAND_LOGO_WHITE_PATH", "img/AnunciateYa_Logo_White.png"
        ),
        "brand_favicon": getattr(
            settings, "BRAND_FAVICON_PATH", "img/AnunciateYa_Favicon.png"
        ),
        "brand_hero_bg": getattr(
            settings,
            "BRAND_HERO_BG_PATH",
            "img/AnunciateYa_HeroBackground.webp",
        ),
        "brand_fonts_url": _brand_font_stylesheet_url(),
        "brand_theme_color": getattr(settings, "BRAND_THEME_COLOR", "#3CBB6B"),
        "google_tag_manager_id": _google_tag_manager_id_for_request(request),
        "inject_ga4_gtag": _analytics_surface_allowed(request),
        "meta_pixel_id": _meta_pixel_id_for_request(request),
        "facebook_domain_verification": (
            getattr(settings, "FACEBOOK_DOMAIN_VERIFICATION", "") or ""
        ).strip(),
        "footer_social_links": _footer_social_links(),
    }
    context.update(_hosting_alert_context(request))
    return context
