from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("inicio/", RedirectView.as_view(url="/", permanent=True), name="home"),
    path("terminos/", views.terms_of_service, name="terms"),
    path("privacidad/", views.privacy_policy, name="privacy"),
    path("newsletter/", views.newsletter_signup, name="newsletter_signup"),
]
