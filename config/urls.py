"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core import views as core_views
from apps.core.sitemaps import sitemaps
from apps.listings import views as listings_views

urlpatterns = [
    path("health/", core_views.healthcheck, name="health"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("llms.txt", core_views.llms_txt, name="llms_txt"),
    path("", core_views.home, name="root_home"),
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
        "api/motorcycle-models/",
        listings_views.motorcycle_model_options,
        name="motorcycle_model_options",
    ),
    path(
        "api/electronics-models/",
        listings_views.electronics_model_options,
        name="electronics_model_options",
    ),
    path(
        "api/electronics-brands/",
        listings_views.electronics_brand_options,
        name="electronics_brand_options",
    ),
    path(
        "api/home-models/",
        listings_views.homegoods_model_options,
        name="homegoods_model_options",
    ),
    path(
        "api/home-brands/",
        listings_views.homegoods_brand_options,
        name="homegoods_brand_options",
    ),
    path(
        "vehiculos/",
        RedirectView.as_view(url="/autos/", permanent=True),
    ),
    path(
        "electronics/",
        RedirectView.as_view(url="/electronica/", permanent=True),
    ),
    # Listing detail (SEO): /autos/hyundai-tucson-2019-73/
    path(
        "<slug:category_slug>/<slug:listing_slug>/",
        listings_views.listing_detail_seo,
        name="listing_detail_seo",
    ),
    # Legacy /inicio/ redirect before category catch-all.
    path("", include("apps.core.urls", namespace="core")),
    path(
        "<slug:slug>/",
        listings_views.category_landing,
        name="category_landing",
    ),
]

handler404 = "apps.core.views.page_not_found"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
