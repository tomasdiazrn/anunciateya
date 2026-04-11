from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
class Review(models.Model):
    """Review of a seller in context of a completed transaction / listing."""

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reviewer", "seller"],
                name="unique_review_per_reviewer_seller",
            ),
        ]
        indexes = [
            models.Index(fields=["seller", "-created_at"]),
            models.Index(fields=["listing"]),
        ]

    def __str__(self):
        return f"Review {self.rating}★ for {self.seller_id}"


class ListingReport(models.Model):
    """User-submitted flag on a listing (moderation queue in admin)."""

    class Reason(models.TextChoices):
        SCAM = "scam", "Estafa o fraude"
        SPAM = "spam", "Spam"
        INCORRECT = "incorrect", "Información incorrecta o engañosa"

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
    created_at = models.DateTimeField(auto_now_add=True)

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
        ]

    def __str__(self):
        return f"Report {self.reason} on listing {self.listing_id}"
