from django.apps import AppConfig


class ListingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.listings"
    label = "listings"
    verbose_name = "Listings"

    def ready(self) -> None:
        from .category_engine_validation import validate_category_engine_at_startup

        validate_category_engine_at_startup()
