from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from apps.categories.services import (
    preferred_explore_category,
    root_categories_for_homepage_annotated,
)
from apps.listings.models import Listing

from .forms import WaitlistForm
from .models import WaitlistSignup
from .seo_copy import CATEGORY_EXPLORE_LABELS


def _explore_listings_target():
    """Landing SEO para CTA 'Explorar': categoría raíz con más anuncios publicados."""
    cat = preferred_explore_category()
    if cat:
        return cat.get_absolute_url(), cat.slug
    return reverse("listings:list"), "listings"


def home(request):
    """Home: categorías solo desde Category (orden, icono, descripción en BD)."""
    homepage_limit = 6
    homepage_categories = root_categories_for_homepage_annotated(homepage_limit)
    hero_bits = [c.name.lower() for c in homepage_categories[:3]]
    home_hero_sub = (
        ", ".join(hero_bits) + " y más"
        if hero_bits
        else "Tu mercado local"
    )

    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    published_listing_count = Listing.objects.published().count()
    explore_listings_url, explore_event_slug = _explore_listings_target()

    return render(
        request,
        "core/home.html",
        {
            "homepage_categories": homepage_categories,
            "search_categories": homepage_categories,
            "category_explore_labels": CATEGORY_EXPLORE_LABELS,
            "published_listing_count": published_listing_count,
            "explore_listings_url": explore_listings_url,
            "explore_event_slug": explore_event_slug,
            "home_hero_sub": home_hero_sub,
            "meta_title": f"{brand} — Compra y vende seguro en tu ciudad",
            "meta_description": (
                f"Compra y vende en {city} con {brand}: anuncios locales, vendedores con "
                f"confianza visible y contacto por mensaje. Menos riesgo, más claridad."
            ),
        },
    )


def _waitlist_redirect_after_valid(form, source: str):
    """Guarda lista de espera o redirige si el correo ya existe."""
    email = form.cleaned_data["email"]
    whatsapp = (form.cleaned_data.get("whatsapp") or "").strip()
    if WaitlistSignup.objects.filter(email__iexact=email).exists():
        return redirect(f"{reverse('root_landing')}?waitlist=exists")
    try:
        WaitlistSignup.objects.create(email=email, whatsapp=whatsapp, source=source)
    except IntegrityError:
        return redirect(f"{reverse('root_landing')}?waitlist=exists")
    return redirect(f"{reverse('root_landing')}?waitlist=ok")


def healthcheck(_request):
    return HttpResponse("ok", content_type="text/plain")


def _honeypot_filled(form) -> bool:
    return bool((form.cleaned_data.get("company_url") or "").strip())


def coming_soon(request):
    """Landing pre-lanzamiento: lista de espera, independiente del home."""
    brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
    city = getattr(settings, "SEO_MARKET_CITY", "Guayaquil")
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    path = (request.path or "/").rstrip("/") or "/"
    if path == "/proximamente":
        canonical_href_override = f"{site_url}/proximamente/"
    else:
        canonical_href_override = f"{site_url}/"

    if request.method == "POST":
        if "hero-email" in request.POST:
            form_hero = WaitlistForm(request.POST, prefix="hero")
            form_cta = WaitlistForm(prefix="cta")
            if form_hero.is_valid():
                if _honeypot_filled(form_hero):
                    return redirect(f"{reverse('root_landing')}?waitlist=ok")
                return _waitlist_redirect_after_valid(form_hero, "hero")
        elif "cta-email" in request.POST:
            form_cta = WaitlistForm(request.POST, prefix="cta")
            form_hero = WaitlistForm(prefix="hero")
            if form_cta.is_valid():
                if _honeypot_filled(form_cta):
                    return redirect(f"{reverse('root_landing')}?waitlist=ok")
                return _waitlist_redirect_after_valid(form_cta, "cta")
        else:
            form_hero = WaitlistForm(prefix="hero")
            form_cta = WaitlistForm(prefix="cta")
    else:
        form_hero = WaitlistForm(prefix="hero")
        form_cta = WaitlistForm(prefix="cta")

    meta_title = f"{brand} — Próximamente en {city} | Lista de espera"
    meta_description = (
        f"Únete a la lista de espera de {brand}: compra y venta local en {city}, "
        f"sin comisiones, publicación gratis y contacto directo. Lanzamiento próximo."
    )

    return render(
        request,
        "core/coming_soon.html",
        {
            "form_hero": form_hero,
            "form_cta": form_cta,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "canonical_href_override": canonical_href_override,
        },
    )
