"""Production settings."""
import os
import urllib.parse

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
MIDDLEWARE.append("apps.core.middleware.ContentSecurityPolicyMiddleware")

RATELIMIT_ENABLE = True

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set in production."
    )

result = urllib.parse.urlparse(DATABASE_URL)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": result.path[1:],
        "USER": result.username,
        "PASSWORD": result.password,
        "HOST": result.hostname,
        "PORT": result.port,
        "CONN_MAX_AGE": config("POSTGRES_CONN_MAX_AGE", default=60, cast=int),
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@anunciateya.com")

AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="").strip()
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-1").strip()
AWS_S3_MEDIA_LOCATION = config("AWS_S3_MEDIA_LOCATION", default="media").strip().strip("/")
AWS_S3_CUSTOM_DOMAIN = config("AWS_S3_CUSTOM_DOMAIN", default="").strip().rstrip("/")
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": config(
        "AWS_S3_MEDIA_CACHE_CONTROL",
        default="public, max-age=31536000, immutable",
    )
}
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = config("AWS_QUERYSTRING_AUTH", default=False, cast=bool)
AWS_S3_FILE_OVERWRITE = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = True
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

if AWS_STORAGE_BUCKET_NAME:
    s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME,
        "location": AWS_S3_MEDIA_LOCATION,
        "object_parameters": AWS_S3_OBJECT_PARAMETERS,
        "default_acl": AWS_DEFAULT_ACL,
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "file_overwrite": AWS_S3_FILE_OVERWRITE,
    }
    if AWS_S3_CUSTOM_DOMAIN:
        s3_options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": s3_options,
    }

    if AWS_S3_CUSTOM_DOMAIN:
        media_prefix = f"{AWS_S3_MEDIA_LOCATION}/" if AWS_S3_MEDIA_LOCATION else ""
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{media_prefix}"
