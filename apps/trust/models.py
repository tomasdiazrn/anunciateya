from django.conf import settings
from django.db import models


class ListingReport(models.Model):
    """User-submitted flag on a listing (moderation queue in admin)."""

    class Reason(models.TextChoices):
        SCAM = "scam", "Estafa o fraude"
        SPAM = "spam", "Spam"
        INCORRECT = "incorrect", "Información incorrecta o engañosa"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        REVIEWED = "reviewed", "Revisado"
        ACTIONED = "actioned", "Acción tomada"
        DISMISSED = "dismissed", "Descartado"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listing_reports_made",
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="listing_reports_reviewed",
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "listing"],
                name="unique_report_per_user_per_listing",
            ),
        ]
        indexes = [
            models.Index(fields=["listing", "-created_at"]),
            models.Index(fields=["reason", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Report {self.reason} on listing {self.listing_id}"
