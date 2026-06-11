# Backfill icon + order for categories created after 0003 (e.g. seed_mvp_data).

from django.db import migrations


def backfill_category_display(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    slug_meta = {
        "autos": {"icon": "fa-solid fa-car-side", "order": 1},
        "inmuebles": {"icon": "fa-solid fa-house", "order": 2},
        "electronica": {"icon": "fa-solid fa-mobile-screen-button", "order": 3},
        "motos": {"icon": "fa-solid fa-motorcycle", "order": 4},
        "hogar": {"icon": "fa-solid fa-couch", "order": 5},
        "instrumentos": {"icon": "fa-solid fa-guitar", "order": 6},
    }
    for cat in Category.objects.all():
        slug = (cat.slug or "").lower()
        meta = slug_meta.get(slug)
        if meta:
            cat.icon = meta["icon"]
            cat.order = meta["order"]
            cat.save(update_fields=["icon", "order"])
        elif cat.order == 0:
            cat.order = 50
            cat.save(update_fields=["order"])


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0003_category_display_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_category_display, migrations.RunPython.noop),
    ]
