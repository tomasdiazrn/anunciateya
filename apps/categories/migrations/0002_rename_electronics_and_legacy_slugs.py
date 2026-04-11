# Datos: categorías en español y slug estable para autos.

from django.db import migrations


def forwards(apps, schema_editor):
    Category = apps.get_model("categories", "Category")

    # electronics → electrónica (slug electronica)
    for c in Category.objects.filter(slug__iexact="electronics"):
        if Category.objects.filter(slug="electronica").exclude(pk=c.pk).exists():
            continue
        c.name = "Electrónica"
        c.slug = "electronica"
        if not (c.description or "").strip():
            c.description = (
                "Celulares, computación y electrodomésticos en tu zona."
            )
        c.save()

    # Legado: vehiculos → autos (si no hay ya una fila "autos")
    if not Category.objects.filter(slug="autos").exists():
        leg = Category.objects.filter(slug="vehiculos").first()
        if leg:
            leg.name = "Autos"
            leg.slug = "autos"
            leg.save()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
