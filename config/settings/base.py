"""
Base Django settings for AnunciateYa (anunciateya.com).
Environment-specific modules import this and override as needed.
"""
from pathlib import Path

from decouple import config

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
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.HtmxClientRedirectMiddleware",
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

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "es"
# Sitio monolingüe: solo español (evita mensajes en inglés si el navegador pide otro idioma).
LANGUAGES = [("es", "Español")]
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
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
LOGOUT_REDIRECT_URL = "root_home"

PUBLIC_SITE_DOMAIN = "anunciateya.com"
PUBLIC_SITE_URL = "https://anunciateya.com"
SITE_NAME = PUBLIC_SITE_DOMAIN
SITE_URL = PUBLIC_SITE_URL
# Marca y ciudad para títulos SEO (sitio monolingüe español).
SEO_BRAND_NAME = "AnunciateYa"
SEO_MARKET_CITY = "Guayaquil"
SOCIAL_SHARE_IMAGE_PATH = "img/AnunciateYa_ShareImage_Home.png"
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@anunciateya.com")
EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default=SEO_BRAND_NAME)
CONTACT_EMAIL = config("CONTACT_EMAIL", default="hola@anunciateya.com")

# Hosting membership (custom admin panel only; configured per client/project).
HOSTING_MEMBERSHIP_START_DATE = config(
    "HOSTING_MEMBERSHIP_START_DATE",
    default="",
).strip()
HOSTING_MEMBERSHIP_EXPIRES_DATE = config(
    "HOSTING_MEMBERSHIP_EXPIRES_DATE",
    default="",
).strip()
HOSTING_RENEWAL_URL = config(
    "HOSTING_RENEWAL_URL",
    default="https://altovalleit.com/hosting/",
).strip()

# OTP login product rules. These are not secrets or environment-specific config.
USER_OTP_EXPIRY_MINUTES = 10
USER_OTP_MAX_ATTEMPTS = 5
USER_OTP_SEND_LIMIT = 3
USER_OTP_SEND_WINDOW_MINUTES = 15
USER_OTP_RESEND_COOLDOWN_SECONDS = 60
USER_OTP_ATTEMPT_COOLDOWN_MINUTES = 5
USER_OTP_SESSION_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_AGE = USER_OTP_SESSION_AGE
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
USER_PUBLIC_PROFILE_LINKS_ENABLED = config(
    "USER_PUBLIC_PROFILE_LINKS_ENABLED",
    default=False,
    cast=bool,
)

# Identidad visual pública (rutas relativas a static/)
BRAND_LOGO_PATH = config("BRAND_LOGO_PATH", default="img/AnunciateYa_Logo.png")
BRAND_LOGO_WHITE_PATH = config(
    "BRAND_LOGO_WHITE_PATH",
    default="img/AnunciateYa_Logo_White.png",
)
BRAND_FAVICON_PATH = config("BRAND_FAVICON_PATH", default="img/AnunciateYa_Favicon.png")
BRAND_HERO_BG_PATH = config(
    "BRAND_HERO_BG_PATH",
    default="img/AnunciateYa_HeroBackground.webp",
)
BRAND_FONT_DISPLAY = config("BRAND_FONT_DISPLAY", default="General Sans")
BRAND_FONT_BODY = config("BRAND_FONT_BODY", default="General Sans")
BRAND_THEME_COLOR = config("BRAND_THEME_COLOR", default="#3CBB6B")

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
