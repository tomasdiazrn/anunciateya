from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_delete_waitlistsignup"),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsletterSubscriber",
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
                    "email",
                    models.EmailField(
                        db_index=True,
                        max_length=254,
                        unique=True,
                        verbose_name="correo",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name="fecha de suscripción",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
            ],
            options={
                "verbose_name": "Suscriptor newsletter",
                "verbose_name_plural": "Suscriptores newsletter",
                "ordering": ["-created_at"],
            },
        ),
    ]
