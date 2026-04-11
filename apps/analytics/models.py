from django.conf import settings
from django.db import models


class Event(models.Model):
    """Evento de uso interno (clics con data-event en plantillas)."""

    event_type = models.CharField(max_length=120, db_index=True)
    event_detail = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_events",
    )
    path = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} · {self.created_at:%Y-%m-%d %H:%M}"
