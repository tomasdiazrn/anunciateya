from django.urls import path
from django.views.generic import RedirectView


app_name = "users_legacy"


urlpatterns = [
    path("login/", RedirectView.as_view(url="/ingresar/", permanent=True)),
    path("register/", RedirectView.as_view(url="/registrarse/", permanent=True)),
    path("logout/", RedirectView.as_view(url="/salir/", permanent=True)),
    path("password-reset/", RedirectView.as_view(url="/recuperar-clave/", permanent=True)),
    path("password-reset/done/", RedirectView.as_view(url="/recuperar-clave/enviado/", permanent=True)),
    path(
        "password-reset/<uidb64>/<token>/",
        RedirectView.as_view(url="/recuperar-clave/%(uidb64)s/%(token)s/", permanent=True),
    ),
    path("password-reset/complete/", RedirectView.as_view(url="/recuperar-clave/completa/", permanent=True)),
    path("verify-phone/", RedirectView.as_view(url="/verificar-telefono/", permanent=True)),
    path("profiles/<int:pk>/", RedirectView.as_view(url="/perfiles/%(pk)s/", permanent=True)),
]

