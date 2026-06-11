from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("listings", "0026_sync_market_taxonomy_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingLead",
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
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("form", "Formulario"),
                            ("whatsapp", "WhatsApp"),
                        ],
                        db_index=True,
                        default="form",
                        max_length=20,
                    ),
                ),
                ("buyer_name", models.CharField(blank=True, max_length=120)),
                ("buyer_email", models.EmailField(blank=True, max_length=254)),
                ("message", models.TextField(blank=True)),
                (
                    "email_status",
                    models.CharField(
                        choices=[
                            ("not_applicable", "No aplica"),
                            ("pending", "Pendiente"),
                            ("sent", "Enviado"),
                            ("failed", "Falló"),
                        ],
                        db_index=True,
                        default="not_applicable",
                        max_length=20,
                    ),
                ),
                ("email_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "buyer_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="listing_leads_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leads",
                        to="listings.listing",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="listing_leads_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["seller", "-created_at"],
                        name="listings_li_seller__96e42a_idx",
                    ),
                    models.Index(
                        fields=["listing", "-created_at"],
                        name="listings_li_listing_1e110a_idx",
                    ),
                    models.Index(
                        fields=["source", "-created_at"],
                        name="listings_li_source_c6680b_idx",
                    ),
                    models.Index(
                        fields=["email_status", "-created_at"],
                        name="listings_li_email_s_f8995c_idx",
                    ),
                ],
            },
        ),
    ]
