from django.urls import path
from django.views.generic import RedirectView


app_name = "users_legacy"


urlpatterns = [
    path("login/", RedirectView.as_view(url="/ingresar/", permanent=True)),
    path("register/", RedirectView.as_view(url="/registrarse/", permanent=True)),
    path("logout/", RedirectView.as_view(url="/salir/", permanent=True)),
    path("verify-phone/", RedirectView.as_view(url="/verificar-telefono/", permanent=True)),
    path("profiles/<int:pk>/", RedirectView.as_view(url="/perfiles/%(pk)s/", permanent=True)),
]

