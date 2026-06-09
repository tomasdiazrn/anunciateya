"""
Central Django settings entrypoint.

Set DJANGO_ENV=production to load production settings; development is the
default so local management commands keep working without extra setup.
"""
from django.core.exceptions import ImproperlyConfigured
from decouple import config

DJANGO_ENV = config("DJANGO_ENV", default="development").strip().lower()

if DJANGO_ENV in {"development", "dev", "local"}:
    from .development import *  # noqa: F403
elif DJANGO_ENV in {"production", "prod"}:
    from .production import *  # noqa: F403
else:
    raise ImproperlyConfigured(
        "DJANGO_ENV must be one of: development, dev, local, production, prod."
    )
