from django.urls import path

from . import views

app_name = "adminapp"

urlpatterns = [
    path("login/", views.admin_login_redirect, name="login"),
    path("logout/", views.admin_logout_view, name="logout"),
    path("", views.dashboard_view, name="dashboard"),
    path("hosting/", views.hosting_view, name="hosting"),
    path("anuncios/publicar/", views.admin_listing_publish_view, name="listing_publish"),
    path(
        "anuncios/publicar/<slug:category_slug>/",
        views.admin_listing_publish_in_category_view,
        name="listing_publish_in_category",
    ),
    path("anuncios/", views.admin_listings_view, name="listings"),
    path("anuncios/<int:pk>/", views.admin_listing_detail_view, name="listing_detail"),
    path(
        "anuncios/<int:pk>/set-status/",
        views.admin_listing_set_status,
        name="listing_set_status",
    ),
    path(
        "anuncios/<int:pk>/archive/",
        views.admin_listing_archive,
        name="listing_archive",
    ),
    path(
        "anuncios/<int:pk>/unarchive/",
        views.admin_listing_unarchive,
        name="listing_unarchive",
    ),
    path(
        "anuncios/<int:pk>/delete/",
        views.admin_listing_delete,
        name="listing_delete",
    ),
    path("usuarios/", views.admin_users_view, name="users"),
    path(
        "usuarios/<int:pk>/delete/",
        views.admin_user_delete_view,
        name="user_delete",
    ),
    path(
        "usuarios/<int:pk>/toggle-active/",
        views.admin_user_toggle_active_view,
        name="user_toggle_active",
    ),
    path(
        "newsletter/",
        views.admin_newsletter_subscribers_view,
        name="newsletter_subscribers",
    ),
    path(
        "newsletter/<int:pk>/toggle-active/",
        views.admin_newsletter_subscriber_toggle_active_view,
        name="newsletter_subscriber_toggle_active",
    ),
    path("usuarios/<int:pk>/", views.admin_user_detail_view, name="user_detail"),
]
