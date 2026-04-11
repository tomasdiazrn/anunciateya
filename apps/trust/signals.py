"""Invalidate per-seller trust cache when reviews or verification change."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.users.models import UserVerification

from .models import Review
from .services import invalidate_seller_trust_cache


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def trust_cache_on_review_change(sender, instance, **kwargs):
    invalidate_seller_trust_cache(instance.seller_id)


@receiver(post_save, sender=UserVerification)
@receiver(post_delete, sender=UserVerification)
def trust_cache_on_verification_change(sender, instance, **kwargs):
    invalidate_seller_trust_cache(instance.user_id)
