from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0013_rename_listings_pr_propert_idx_listings_pr_propert_dc1e5b_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="motorcyclelisting",
            name="mileage",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Kilometraje",
            ),
        ),
        migrations.AddField(
            model_name="motorcyclelisting",
            name="transmission",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("automatico", "Automático"),
                    ("otro", "Otro"),
                ],
                default="manual",
                max_length=20,
                verbose_name="Transmisión",
            ),
        ),
        migrations.AddField(
            model_name="motorcyclelisting",
            name="fuel_type",
            field=models.CharField(
                choices=[
                    ("gasolina", "Gasolina"),
                    ("nafta", "Nafta"),
                    ("electrica", "Eléctrica"),
                    ("otro", "Otro"),
                ],
                default="gasolina",
                max_length=20,
                verbose_name="Combustible",
            ),
        ),
        migrations.AddIndex(
            model_name="motorcyclelisting",
            index=models.Index(fields=["year"], name="listings_mo_year_idx"),
        ),
        migrations.AddIndex(
            model_name="motorcyclelisting",
            index=models.Index(fields=["brand"], name="listings_mo_brand_idx"),
        ),
        migrations.AddIndex(
            model_name="motorcyclelisting",
            index=models.Index(fields=["model"], name="listings_mo_model_idx"),
        ),
    ]
