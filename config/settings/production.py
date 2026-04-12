"""Production settings — set DJANGO_SETTINGS_MODULE=config.settings.production on the server."""
from django.core.exceptions import ImproperlyConfigured
from decouple import Csv, UndefinedValueError, config

from . import base as _base_settings
from .base import *  # noqa: F403

DEBUG = False

try:
    SECRET_KEY = config("SECRET_KEY")
except UndefinedValueError as exc:
    raise ImproperlyConfigured(
        "SECRET_KEY must be set in the environment for production."
    ) from exc

ALLOWED_HOSTS = [h.strip() for h in config("ALLOWED_HOSTS", cast=Csv()) if h.strip()]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be set and non-empty in production."
    )

MIDDLEWARE = list(_base_settings.MIDDLEWARE)
MIDDLEWARE.insert(1, "apps.core.middleware.LandingOnlyMiddleware")
MIDDLEWARE.append("apps.core.middleware.ContentSecurityPolicyMiddleware")

LANDING_ONLY_ENABLED = config("LANDING_ONLY_ENABLED", default=False, cast=bool)
RATELIMIT_ENABLE = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": config("POSTGRES_CONN_MAX_AGE", default=60, cast=int),
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@anunciateya.com")

# Redirects raros a https://127.0.0.1: suele ser SECURE_SSL_REDIRECT=True + petición HTTP
# con Host=127.0.0.1 (curl directo a Gunicorn) o proxy sin X-Forwarded-Proto: https.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "production-ratelimit",
    }
}

# Opción A (producción estable): sin manifest strict en {% static %}.
# - Evita ValueError si staticfiles.json falta (p. ej. volumen Docker sobre STATIC_ROOT).
# - No rompe plantillas; encaja si Nginx ya sirve /static/.
# Se hace merge con STORAGES de base para conservar "default" (media).
STORAGES = {
    **STORAGES,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
