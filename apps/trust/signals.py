"""Keep trust cache and listing moderation flags in sync."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.users.models import UserVerification

from .models import ListingReport
from .services import invalidate_seller_verification_cache, sync_listing_flag


@receiver(post_save, sender=UserVerification)
@receiver(post_delete, sender=UserVerification)
def trust_cache_on_verification_change(sender, instance, **kwargs):
    invalidate_seller_verification_cache(instance.user_id)


@receiver(post_save, sender=ListingReport)
@receiver(post_delete, sender=ListingReport)
def listing_flag_on_report_change(sender, instance, **kwargs):
    sync_listing_flag(instance.listing_id)
