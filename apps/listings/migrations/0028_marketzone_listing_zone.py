from django.db import migrations, models
import django.db.models.deletion


MARKET_ZONES = [
    ("urdesa", "Urdesa", "Guayaquil", "urban", 10),
    ("kennedy", "Kennedy", "Guayaquil", "urban", 20),
    ("alborada", "Alborada", "Guayaquil", "urban", 30),
    ("garzota", "Garzota", "Guayaquil", "urban", 40),
    ("sauces", "Sauces", "Guayaquil", "urban", 50),
    ("samanes", "Samanes", "Guayaquil", "urban", 60),
    ("ceibos", "Ceibos", "Guayaquil", "urban", 70),
    ("via-a-la-costa", "Vía a la Costa", "Guayaquil", "suburban", 80),
    ("puerto-santa-ana", "Puerto Santa Ana", "Guayaquil", "urban", 90),
    ("centro", "Centro", "Guayaquil", "urban", 100),
    ("norte-centro", "Norte centro", "Guayaquil", "urban", 110),
    ("sur", "Sur", "Guayaquil", "urban", 120),
    ("mapasingue", "Mapasingue", "Guayaquil", "urban", 130),
    ("via-daule", "Vía Daule", "Guayaquil", "suburban", 140),
    ("entrada-de-la-8", "Entrada de la 8", "Guayaquil", "urban", 150),
    ("florida", "Florida", "Guayaquil", "urban", 160),
    ("bastion-popular", "Bastión Popular", "Guayaquil", "urban", 170),
    ("guayacanes", "Guayacanes", "Guayaquil", "urban", 180),
    ("mucho-lote", "Mucho Lote", "Guayaquil", "urban", 190),
    ("la-joya", "La Joya", "Daule", "nearby_city", 200),
    ("samborondon", "Samborondón", "Samborondón", "nearby_city", 210),
    ("duran", "Durán", "Durán", "nearby_city", 220),
    ("nobol", "Nobol", "Nobol", "nearby_city", 230),
    ("otro-guayaquil", "Otro sector de Guayaquil", "Guayaquil", "other", 999),
]


def seed_market_zones(apps, schema_editor):
    MarketZone = apps.get_model("listings", "MarketZone")
    Listing = apps.get_model("listings", "Listing")
    zone_by_slug = {}
    for slug, name, city, zone_type, sort_order in MARKET_ZONES:
        zone, _ = MarketZone.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "city": city,
                "zone_type": zone_type,
                "sort_order": sort_order,
                "is_active": True,
            },
        )
        zone_by_slug[slug] = zone
    default_zone = zone_by_slug["otro-guayaquil"]
    Listing.objects.filter(zone__isnull=True).update(zone=default_zone)


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0027_listing_lead"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketZone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(db_index=True, max_length=100, unique=True)),
                ("slug", models.SlugField(unique=True)),
                ("city", models.CharField(db_index=True, default="Guayaquil", max_length=100)),
                (
                    "zone_type",
                    models.CharField(
                        choices=[
                            ("urban", "Urbana"),
                            ("suburban", "Periferia"),
                            ("nearby_city", "Ciudad cercana"),
                            ("other", "Otro"),
                        ],
                        db_index=True,
                        default="urban",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "ordering": ["sort_order", "name"],
                "indexes": [
                    models.Index(
                        fields=["city", "is_active", "sort_order"],
                        name="listings_ma_city_fabafe_idx",
                    ),
                    models.Index(
                        fields=["zone_type", "is_active"],
                        name="listings_ma_zone_ty_d579aa_idx",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="listing",
            name="location_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="zone",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="listings",
                to="listings.marketzone",
            ),
        ),
        migrations.RunPython(seed_market_zones, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="listing",
            name="location",
        ),
        migrations.AlterField(
            model_name="listing",
            name="zone",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="listings",
                to="listings.marketzone",
            ),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(
                fields=["zone", "-created_at"],
                name="listings_li_zone_id_fdd029_idx",
            ),
        ),
    ]
