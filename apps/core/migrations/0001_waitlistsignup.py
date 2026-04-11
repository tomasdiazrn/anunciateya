from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WaitlistSignup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254, unique=True, verbose_name="correo")),
                ("whatsapp", models.CharField(blank=True, default="", max_length=40, verbose_name="WhatsApp")),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        help_text="hero o cta (formulario usado).",
                        max_length=8,
                        verbose_name="origen",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
            ],
            options={
                "verbose_name": "Inscripción lista de espera",
                "verbose_name_plural": "Lista de espera (próximamente)",
                "ordering": ("-created_at",),
            },
        ),
    ]
