"""
Base Django settings for AnunciateYa (anunciateya.com).
Environment-specific modules import this and override as needed.
"""
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Override in production via environment; default allows manage.py to run before .env exists.
SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-only-set-secret-key-in-env")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "django_htmx",
    "apps.core",
    "apps.users",
    "apps.categories",
    "apps.listings",
    "apps.chat",
    "apps.trust",
    "apps.analytics",
    "apps.adminapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_metadata",
                "apps.core.context_processors.footer_nav_categories",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guayaquil"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "listings:list"
LOGOUT_REDIRECT_URL = "core:home"

SITE_NAME = config("SITE_NAME", default="anunciateya.com")
SITE_URL = config("SITE_URL", default="http://127.0.0.1:8000")
# Marca y ciudad para títulos SEO (sitio monolingüe español).
SEO_BRAND_NAME = config("SEO_BRAND_NAME", default="AnunciateYa")
SEO_MARKET_CITY = config("SEO_MARKET_CITY", default="Guayaquil")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@anunciateya.com")

# Demo local: todas las tarjetas/detalle muestran 10 fotos placeholder (picsum.photos).
STOCK_DEMO_LISTING_PHOTOS = config("STOCK_DEMO_LISTING_PHOTOS", default=False, cast=bool)

# Google Tag Manager (e.g. GTM-XXXXXXX). Empty string disables the snippets in templates.
GOOGLE_TAG_MANAGER_ID = config("GOOGLE_TAG_MANAGER_ID", default="GTM-KSQPQ3PZ")
# Request paths for which GTM is never injected (public site only); see site_metadata context processor.
GOOGLE_TAG_MANAGER_EXCLUDED_PATH_PREFIXES = ("/admin/",)

# Meta (Facebook) Pixel — numeric ID from Events Manager. Empty string disables; not loaded when DEBUG=True
# or on paths in GOOGLE_TAG_MANAGER_EXCLUDED_PATH_PREFIXES (same rules as GTM).
META_PIXEL_ID = config("META_PIXEL_ID", default="967148372336400")

# Meta (Facebook) domain verification — meta tag in <head>. Empty string omits the tag.
FACEBOOK_DOMAIN_VERIFICATION = config("FACEBOOK_DOMAIN_VERIFICATION", default="n8la58cezu7afq4v0f07txp84iqppu")

# Redes sociales (footer). Cadena vacía = no se muestra el icono.
SOCIAL_INSTAGRAM_URL = config(
    "SOCIAL_INSTAGRAM_URL",
    default="https://www.instagram.com/anunciateya.ec/",
)
SOCIAL_TIKTOK_URL = config(
    "SOCIAL_TIKTOK_URL",
    default="https://www.tiktok.com/@anunciateya.ec",
)
SOCIAL_YOUTUBE_URL = config("SOCIAL_YOUTUBE_URL", default="")
SOCIAL_LINKEDIN_URL = config("SOCIAL_LINKEDIN_URL", default="")

# django-ratelimit (key="ip"): sin esto, REMOTE_ADDR vacío o XFF multi-hop → 500 en POST.
RATELIMIT_IP_META_KEY = "apps.core.ip_for_ratelimit.client_ip_for_ratelimit"
