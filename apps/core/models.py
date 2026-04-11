from django.db import models


class WaitlistSignup(models.Model):
    """Inscripciones a la lista de espera de /proximamente/."""

    email = models.EmailField("correo", max_length=254, unique=True, db_index=True)
    whatsapp = models.CharField("WhatsApp", max_length=40, blank=True, default="")
    source = models.CharField(
        "origen",
        max_length=8,
        blank=True,
        help_text="hero o cta (formulario usado).",
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Inscripción lista de espera"
        verbose_name_plural = "Lista de espera (próximamente)"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)
