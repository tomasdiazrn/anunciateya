from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("<int:pk>/promote/", views.listing_promote, name="promote"),
    # Legacy browse: /listings/ → 301 to /anuncios/ (preserve querystring)
    path("", views.listing_list_legacy, name="list"),
    # Legacy publish: /listings/create/ → 301 to /publicar/
    path("create/", views.listing_create_legacy, name="create"),
    path("my-listings/", views.my_listings, name="mine"),
    path(
        "categories/<slug:slug>/",
        views.category_legacy_redirect,
        name="category_detail",
    ),
    path("<slug:slug>/edit/", views.listing_edit_legacy_redirect, name="edit"),
    path("<slug:slug>/delete/", views.listing_delete, name="delete"),
    path("<slug:slug>/contact/", views.listing_contact_panel, name="contact"),
    path("<slug:slug>/whatsapp/", views.listing_whatsapp_redirect, name="whatsapp"),
    path("<slug:slug>/report/", views.listing_report, name="report"),
    # Legacy detail: /listings/<slug>/ → 301 to /<category>/<slug>/
    path("<slug:slug>/", views.listing_detail_legacy, name="detail"),
]
