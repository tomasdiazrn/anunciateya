from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.http import require_POST

from apps.analytics.models import Event
from apps.categories.services import root_categories, root_categories_for_homepage_annotated

from .forms import NewsletterSignupForm
from .models import NewsletterSubscriber


QUICK_CATEGORY_SLUGS = ["autos", "inmuebles", "electronica", "motos", "hogar"]


def page_not_found(request, exception=None):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "404.html",
        {
            "meta_title": f"Página no encontrada | {brand}",
            "meta_description": f"No encontramos esa página en {brand}.",
        },
        status=404,
    )


def _quick_search_categories(categories):
    return sorted(
        (c for c in categories if c.slug in QUICK_CATEGORY_SLUGS),
        key=lambda c: QUICK_CATEGORY_SLUGS.index(c.slug),
    )


def home(request):
    """Home: categorías solo desde Category (orden, icono, descripción en BD)."""
    homepage_limit = 6
    homepage_categories = list(root_categories_for_homepage_annotated(homepage_limit))
    quick_search_categories = _quick_search_categories(homepage_categories)

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")

    return render(
        request,
        "core/home.html",
        {
            "homepage_categories": homepage_categories,
            "quick_search_categories": quick_search_categories,
            "meta_title": f"{brand} — Compra y vende seguro en tu ciudad",
            "meta_description": (
                f"Compra y vende en {city} con {brand}: anuncios locales, vendedores con "
                f"confianza visible y contacto por mensaje. Menos riesgo, más claridad."
            ),
        },
    )


def terms_of_service(request):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "core/legal/terms.html",
        {
            "meta_title": f"Términos de Servicio | {brand}",
            "meta_description": (
                f"Conoce los Términos de Servicio que regulan el uso de {brand}."
            ),
        },
    )


def privacy_policy(request):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "core/legal/privacy.html",
        {
            "meta_title": f"Política de Privacidad | {brand}",
            "meta_description": (
                f"Información sobre la privacidad y tratamiento de datos en {brand}."
            ),
        },
    )


def healthcheck(_request):
    return HttpResponse("ok", content_type="text/plain")


def _static_url(path):
    url = static(path)
    if url.startswith(("http://", "https://")):
        return url
    return url if url.startswith("/") else f"/{url}"


def _manifest_icon(path, sizes, purpose="any"):
    return {
        "src": _static_url(path),
        "sizes": sizes,
        "type": "image/png",
        "purpose": purpose,
    }


def webmanifest(_request):
    """PWA manifest generated from the same branding settings used by templates."""
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    icon_path = getattr(settings, "BRAND_PWA_ICON_PATH", "img/AnunciateYa_PWA_Icon.png")
    payload = {
        "name": brand,
        "short_name": brand,
        "description": f"Clasificados locales en {city} con vendedores verificados.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#FFFFFF",
        "theme_color": getattr(settings, "BRAND_THEME_COLOR", "#3CBB6B"),
        "lang": "es",
        "dir": "ltr",
        "categories": ["shopping", "business", "lifestyle"],
        "icons": [
            _manifest_icon(icon_path, "192x192"),
            _manifest_icon(icon_path, "512x512"),
            _manifest_icon(icon_path, "512x512", purpose="maskable"),
        ],
        "shortcuts": [
            {
                "name": "Publicar anuncio",
                "short_name": "Publicar",
                "description": "Crea un nuevo anuncio en AnunciateYa.",
                "url": "/publicar/",
                "icons": [_manifest_icon(icon_path, "192x192")],
            },
            {
                "name": "Ver anuncios",
                "short_name": "Anuncios",
                "description": "Explora clasificados publicados en tu ciudad.",
                "url": "/anuncios/",
                "icons": [_manifest_icon(icon_path, "192x192")],
            },
        ],
    }
    response = JsonResponse(
        payload,
        json_dumps_params={"ensure_ascii": False},
        content_type="application/manifest+json",
    )
    response["Cache-Control"] = "public, max-age=3600"
    return response


def offline(request):
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    return render(
        request,
        "core/offline.html",
        {
            "meta_title": f"Sin conexión | {brand}",
            "meta_description": (
                "No pudimos conectar con el sitio. Revisa tu conexión e intenta de nuevo."
            ),
            "meta_robots": "noindex, nofollow",
        },
    )


def service_worker(request):
    response = render(
        request,
        "core/service_worker.js",
        content_type="application/javascript; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Service-Worker-Allowed"] = "/"
    return response


def robots_txt(_request):
    site_url = getattr(settings, "PUBLIC_SITE_URL", "https://anunciateya.com").rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /events/",
        "Disallow: /health/",
        "Disallow: /api/",
        "Disallow: /newsletter/",
        "Disallow: /ingresar/",
        "Disallow: /salir/",
        "Disallow: /registrarse/",
        "Disallow: /registrarse/verificar/",
        "Disallow: /verificar-telefono/",
        "Disallow: /mi-cuenta/",
        "Disallow: /publicar/",
        "Disallow: /listings/",
        "",
        f"Sitemap: {site_url}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def llms_txt(_request):
    site_url = getattr(settings, "PUBLIC_SITE_URL", "https://anunciateya.com").rstrip("/")
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    category_lines = [
        f"- {category.name}: {site_url}{category.get_absolute_url()}"
        for category in root_categories()
        if category.slug in QUICK_CATEGORY_SLUGS
    ]
    lines = [
        f"# {brand}",
        "",
        (
            f"{brand} es un marketplace de anuncios clasificados en {city} y Ecuador, "
            "enfocado en compra y venta local con señales de confianza para compradores "
            "y vendedores."
        ),
        "",
        "## URLs publicas principales",
        f"- Home: {site_url}/",
        f"- Anuncios: {site_url}/anuncios/",
        f"- Publicar anuncio: {site_url}/publicar/",
        f"- Sitemap XML: {site_url}/sitemap.xml",
        "",
        "## Categorias principales",
        *(category_lines or [f"- Anuncios: {site_url}/anuncios/"]),
        "",
        "## Guia para crawlers",
        (
            "Usa sitemap.xml como fuente canonica de URLs indexables. No uses rutas de "
            "cuenta, autenticacion, admin, APIs, eventos ni flujos internos como fuentes "
            "de contenido publico."
        ),
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def _newsletter_redirect_url(request):
    return (request.META.get("HTTP_REFERER") or "").strip() or "/"


def _record_newsletter_signup_event(request):
    Event.objects.create(
        event_type="newsletter_signup",
        event_detail="footer",
        user=request.user if request.user.is_authenticated else None,
        path=_newsletter_redirect_url(request),
    )


def _render_newsletter_bar(request, form, message="", message_level="success", status=200):
    return render(
        request,
        "components/layout/newsletter_bar.html",
        {
            "newsletter_form": form,
            "newsletter_message": message,
            "newsletter_message_level": message_level,
        },
        status=status,
    )


@require_POST
def newsletter_signup(request):
    form = NewsletterSignupForm(request.POST)
    if not form.is_valid():
        if request.htmx:
            return _render_newsletter_bar(
                request,
                form,
                "Revisá el email e intentá de nuevo.",
                "error",
                status=400,
            )
        messages.error(request, "Revisá el email e intentá de nuevo.")
        return redirect(_newsletter_redirect_url(request))

    email = form.cleaned_data["email"]
    created = False
    reactivated = False
    try:
        with transaction.atomic():
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={"is_active": True},
            )
            if not created and not subscriber.is_active:
                subscriber.is_active = True
                subscriber.save(update_fields=["is_active"])
                reactivated = True
    except IntegrityError:
        NewsletterSubscriber.objects.get(email=email)

    response_form = NewsletterSignupForm()
    if created or reactivated:
        _record_newsletter_signup_event(request)
        message = "Listo. Te sumamos al newsletter de AnunciateYa."
        level = "success"
    else:
        message = "Ese email ya estaba suscrito. Gracias por seguir cerca."
        level = "info"

    if request.htmx:
        return _render_newsletter_bar(request, response_form, message, level)

    if level == "success":
        messages.success(request, message)
    else:
        messages.info(request, message)
    return redirect(_newsletter_redirect_url(request))
