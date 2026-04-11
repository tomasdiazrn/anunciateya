from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0011_seed_vehicle_taxonomy_minimal"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertylisting",
            name="operation_type",
            field=models.CharField(
                blank=True,
                choices=[("venta", "Venta"), ("alquiler", "Alquiler")],
                max_length=20,
                null=True,
                verbose_name="Operación",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="parking_spaces",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="Parqueaderos",
            ),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="furnished",
            field=models.BooleanField(default=False, verbose_name="Amoblado"),
        ),
        migrations.AddField(
            model_name="propertylisting",
            name="property_condition",
            field=models.CharField(
                blank=True,
                choices=[("nuevo", "Nuevo"), ("usado", "Usado")],
                max_length=20,
                null=True,
                verbose_name="Estado",
            ),
        ),
        migrations.AddIndex(
            model_name="propertylisting",
            index=models.Index(
                fields=["property_type"],
                name="listings_pr_propert_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="propertylisting",
            index=models.Index(
                fields=["operation_type"],
                name="listings_pr_operati_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="propertylisting",
            index=models.Index(
                fields=["area_m2"],
                name="listings_pr_area_m2_idx",
            ),
        ),
    ]
