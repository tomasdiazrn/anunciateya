from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "users"

urlpatterns = [
    path("ingresar/", views.email_login_view, name="login"),
    path("salir/", views.EmailLogoutView.as_view(), name="logout"),
    path("registrarse/", views.RegisterView.as_view(), name="register"),
    path("verificar-telefono/", views.verify_phone, name="verify_phone"),
    path(
        "mi-cuenta/anuncios/<slug:slug>/editar/",
        views.listing_edit_dashboard,
        name="account_listing_edit",
    ),
    path(
        "mi-cuenta/anuncios/",
        views.account_dashboard,
        kwargs={"section": "listings"},
        name="account_listings",
    ),
    path(
        "mi-cuenta/publicar/otros/",
        RedirectView.as_view(url="/mi-cuenta/publicar/", permanent=False),
        name="account_publish_generic",
    ),
    path(
        "mi-cuenta/publicar/<slug:category_slug>/",
        views.listing_publish_in_category_dashboard,
        name="account_publish_in_category",
    ),
    path(
        "mi-cuenta/publicar/",
        views.listing_create_dashboard,
        name="account_publish",
    ),
    path(
        "mi-cuenta/perfil/",
        RedirectView.as_view(pattern_name="users:account", permanent=True),
        name="account_profile",
    ),
    path(
        "mi-cuenta/",
        views.account_dashboard,
        kwargs={"section": "overview"},
        name="account",
    ),
    path("perfiles/<int:pk>/", views.profile_detail, name="profile"),
]
