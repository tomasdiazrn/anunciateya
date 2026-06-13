from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0028_marketzone_listing_zone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="listing",
            name="zone",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="listings",
                to="listings.marketzone",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="address_line",
            field=models.CharField(blank=True, max_length=180, verbose_name="Dirección"),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="address_place_label",
            field=models.CharField(
                blank=True,
                max_length=180,
                verbose_name="Nombre del lugar o edificio",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Latitud",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                verbose_name="Longitud",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="location_precision",
            field=models.CharField(
                choices=[
                    ("sector", "Solo sector"),
                    ("approximate", "Aproximada"),
                    ("exact", "Exacta"),
                ],
                default="sector",
                max_length=20,
                verbose_name="Visibilidad de ubicación",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="geocoding_provider",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="geocoding_place_id",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="geocoded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="propertylisting",
            index=models.Index(
                fields=["location_precision"],
                name="listings_pr_locatio_b3df33_idx",
            ),
        ),
    ]
