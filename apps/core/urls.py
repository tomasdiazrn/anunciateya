from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("inicio/", views.home, name="home"),
]
