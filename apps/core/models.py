from django.db import models


class NewsletterSubscriber(models.Model):
    email = models.EmailField("correo", unique=True, db_index=True)
    created_at = models.DateTimeField("fecha de suscripción", auto_now_add=True)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Suscriptor newsletter"
        verbose_name_plural = "Suscriptores newsletter"

    def __str__(self):
        return self.email
