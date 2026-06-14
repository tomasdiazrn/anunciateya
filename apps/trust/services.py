"""Seller phone verification and moderation hooks."""

from django.core.cache import cache
from apps.users.models import UserVerification

from .models import ListingReport

# Per-seller verification bundle cache (TTL 5 min). Invalidated on verification changes.
VERIFICATION_CACHE_TTL = 300
VERIFICATION_CACHE_KEY = "seller-verification:bundle:{id}"


def invalidate_seller_verification_cache(seller_id: int) -> None:
    """Call when phone verification affecting this seller changes."""
    cache.delete(VERIFICATION_CACHE_KEY.format(id=int(seller_id)))


def _bundle_from_parts(
    *,
    verified: bool,
) -> dict:
    return {
        "verified": verified,
    }


def _compute_bulk_seller_verification(seller_ids: set[int]) -> dict:
    """Uncached verification bundles for a set of seller IDs."""
    if not seller_ids:
        return {}

    verified_ids = set(
        UserVerification.objects.filter(
            user_id__in=seller_ids,
            phone_verified=True,
        ).values_list("user_id", flat=True)
    )

    out = {}
    for sid in seller_ids:
        out[sid] = _bundle_from_parts(
            verified=sid in verified_ids,
        )
    return out


def bulk_seller_verification(seller_ids):
    """
    Verification bundles for many sellers (cached per seller, TTL 5 min).
    Invalidated via invalidate_seller_verification_cache on verification changes.
    """
    seller_ids = {int(x) for x in seller_ids if x is not None}
    if not seller_ids:
        return {}

    out: dict = {}
    missing: set[int] = set()
    for sid in seller_ids:
        key = VERIFICATION_CACHE_KEY.format(id=sid)
        hit = cache.get(key)
        if hit is not None:
            out[sid] = hit
        else:
            missing.add(sid)

    if missing:
        computed = _compute_bulk_seller_verification(missing)
        for sid, bundle in computed.items():
            cache.set(
                VERIFICATION_CACHE_KEY.format(id=sid),
                bundle,
                VERIFICATION_CACHE_TTL,
            )
            out[sid] = bundle

    return out


def seller_verification_bundle(user):
    """Single-seller verification summary for profile / detail / contact."""
    data = bulk_seller_verification([user.pk])
    return data.get(
        user.pk,
        _bundle_from_parts(
            verified=False,
        ),
    )


def sync_listing_flag(listing_id: int) -> None:
    """Set listing.is_flagged when active report count reaches threshold."""
    from apps.listings.models import Listing

    n = (
        ListingReport.objects.filter(listing_id=listing_id)
        .exclude(status=ListingReport.Status.DISMISSED)
        .count()
    )
    Listing.objects.filter(pk=listing_id).update(is_flagged=(n >= 3))
