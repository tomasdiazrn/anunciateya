# Generated manually — order, icon, image + datos iniciales

from django.db import migrations, models


def seed_order_icon(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    slug_icon = {
        "autos": "fa-solid fa-car-side",
        "inmuebles": "fa-solid fa-house",
        "electronica": "fa-solid fa-mobile-screen-button",
        "motos": "fa-solid fa-motorcycle",
        "hogar": "fa-solid fa-couch",
        "instrumentos": "fa-solid fa-guitar",
    }
    order_map = {s: i for i, s in enumerate(slug_icon.keys(), start=1)}
    for cat in Category.objects.all():
        slug = (cat.slug or "").lower()
        if slug in slug_icon:
            cat.order = order_map[slug]
            cat.icon = slug_icon[slug]
        else:
            if cat.order == 0:
                cat.order = 50
        cat.save(update_fields=["order", "icon"])


class Migration(migrations.Migration):

    dependencies = [
        ("categories", "0002_rename_electronics_and_legacy_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="order",
            field=models.PositiveSmallIntegerField(
                db_index=True,
                default=0,
                help_text="Orden en home y selector de publicar (menor = primero).",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="icon",
            field=models.CharField(
                blank=True,
                help_text="Clases CSS Font Awesome, ej. fa-solid fa-car-side",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="image",
            field=models.ImageField(
                blank=True,
                help_text="Opcional: icono visual en lugar de Font Awesome.",
                null=True,
                upload_to="categories/%Y/%m/",
            ),
        ),
        migrations.AlterModelOptions(
            name="category",
            options={
                "ordering": ["order", "name"],
                "verbose_name_plural": "categories",
            },
        ),
        migrations.RunPython(seed_order_icon, migrations.RunPython.noop),
    ]
