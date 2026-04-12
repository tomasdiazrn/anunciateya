"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core import views as core_views
from apps.listings import views as listings_views

urlpatterns = [
    path("health/", core_views.healthcheck, name="health"),
    # Pre-lanzamiento en raíz (SEO / analytics en /); el home real vive en /inicio/ (apps.core.urls).
    path("", core_views.coming_soon, name="root_landing"),
    # Panel staff; antes del catch-all <slug:slug>/.
    path("admin/", include("apps.adminapp.urls", namespace="adminapp")),
    path("events/", include("apps.analytics.urls", namespace="analytics")),
    # Auth (Spanish canonical) + legacy /accounts/ redirects
    path("", include("apps.users.urls", namespace="users")),
    path("accounts/", include("apps.users.urls_legacy")),
    path("listings/", include("apps.listings.urls", namespace="listings")),
    # Spanish SEO browse entrypoint (keep /listings/ as legacy)
    path("anuncios/", listings_views.listing_list, name="browse"),
    # Publicar: selector y flujos por categoría (legacy /listings/create/ → /publicar/)
    path("publicar/", listings_views.listing_create, name="publish"),
    path(
        "publicar/otros/",
        RedirectView.as_view(url="/publicar/", permanent=False),
        name="publish_generic",
    ),
    path(
        "publicar/<slug:category_slug>/",
        listings_views.create_listing_in_category,
        name="publish_in_category",
    ),
    path(
        "api/vehicle-models/",
        listings_views.vehicle_model_options,
        name="vehicle_model_options",
    ),
    path(
        "vehiculos/",
        RedirectView.as_view(url="/autos/", permanent=True),
    ),
    path(
        "electronics/",
        RedirectView.as_view(url="/electronica/", permanent=True),
    ),
    path(
        "guayaquil/",
        listings_views.location_landing,
        {"location_slug": "guayaquil"},
        name="location_guayaquil",
    ),
    path(
        "samborondon/",
        listings_views.location_landing,
        {"location_slug": "samborondon"},
        name="location_samborondon",
    ),
    # Location + category (SEO): /guayaquil/autos/
    path(
        "guayaquil/<slug:category_slug>/",
        listings_views.location_category_landing,
        {"location_slug": "guayaquil"},
        name="location_guayaquil_category",
    ),
    path(
        "samborondon/<slug:category_slug>/",
        listings_views.location_category_landing,
        {"location_slug": "samborondon"},
        name="location_samborondon_category",
    ),
    # Listing detail (SEO): /autos/hyundai-tucson-2019-73/
    path(
        "<slug:category_slug>/<slug:listing_slug>/",
        listings_views.listing_detail_seo,
        name="listing_detail_seo",
    ),
    path(
        "proximamente/",
        core_views.coming_soon,
        name="coming_soon",
    ),
    # /inicio/ (home) antes del catch-all de categoría <slug>/.
    path("", include("apps.core.urls", namespace="core")),
    path(
        "<slug:slug>/",
        listings_views.category_landing,
        name="category_landing",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
