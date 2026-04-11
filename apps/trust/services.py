"""Reputation aggregation, trust scores, and moderation hooks."""

from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone
from apps.users.models import User, UserVerification

from .models import ListingReport, Review

# Per-seller trust bundle cache (TTL 5 min). Invalidated on review or verification changes.
TRUST_CACHE_TTL = 300
TRUST_CACHE_KEY = "trust:bundle:seller:{id}"


def compute_trust_score_parts(
    *,
    phone_verified: bool,
    review_count: int,
    avg_rating: float | None,
    date_joined,
) -> tuple[int, str]:
    """
    Score 0–100 and label: high (>=70), medium (40–69), low (<40).
    +40 verified phone, +30 if >=5 reviews, +20 if avg >=4, +10 if account >30 days.
    Numeric score is kept in bundles for admin/JSON-LD; UI shows label only.
    """
    score = 0
    if phone_verified:
        score += 40
    if review_count >= 5:
        score += 30
    if avg_rating is not None and float(avg_rating) >= 4:
        score += 20
    if date_joined is not None:
        age_days = (timezone.now() - date_joined).days
        if age_days > 30:
            score += 10
    score = min(score, 100)
    if score >= 70:
        label = "high"
    elif score >= 40:
        label = "medium"
    else:
        label = "low"
    return score, label


def calculate_trust_score(user) -> tuple[int, str]:
    """Compute trust score for a single user (uses DB). For admin/debug tooling."""
    verified = UserVerification.objects.filter(
        user_id=user.pk,
        phone_verified=True,
    ).exists()
    agg = Review.objects.filter(seller_id=user.pk).aggregate(
        avg=Avg("rating"),
        c=Count("id"),
    )
    avg_rating = agg["avg"]
    count = agg["c"] or 0
    return compute_trust_score_parts(
        phone_verified=verified,
        review_count=count,
        avg_rating=float(avg_rating) if avg_rating is not None else None,
        date_joined=user.date_joined,
    )


def invalidate_seller_trust_cache(seller_id: int) -> None:
    """Call when reviews or phone verification affecting this seller change."""
    cache.delete(TRUST_CACHE_KEY.format(id=int(seller_id)))


def _bundle_from_parts(
    *,
    verified: bool,
    avg_rating: float | None,
    review_count: int,
    date_joined,
) -> dict:
    score, label = compute_trust_score_parts(
        phone_verified=verified,
        review_count=review_count,
        avg_rating=avg_rating,
        date_joined=date_joined,
    )
    year = date_joined.year if date_joined else None
    member_since = str(year) if year else ""
    member_since_display = (
        f"Miembro desde {year}" if year else "Cuenta nueva"
    )

    return {
        "verified": verified,
        "avg_rating": round(avg_rating, 1) if avg_rating is not None else None,
        "review_count": review_count,
        "rating_avg": round(avg_rating, 1) if avg_rating is not None else None,
        "rating_count": review_count,
        "member_since": member_since,
        "member_since_display": member_since_display,
        "trust_score": score,
        "trust_label": label,
    }


def _compute_bulk_seller_trust(seller_ids: set[int]) -> dict:
    """Uncached trust bundles for a set of seller IDs."""
    if not seller_ids:
        return {}

    rows = (
        Review.objects.filter(seller_id__in=seller_ids)
        .values("seller_id")
        .annotate(avg=Avg("rating"), c=Count("id"))
    )
    review_by_seller = {row["seller_id"]: row for row in rows}

    verified_ids = set(
        UserVerification.objects.filter(
            user_id__in=seller_ids,
            phone_verified=True,
        ).values_list("user_id", flat=True)
    )

    user_dates = {
        row["id"]: row["date_joined"]
        for row in User.objects.filter(pk__in=seller_ids).values("id", "date_joined")
    }

    out = {}
    for sid in seller_ids:
        rrow = review_by_seller.get(sid)
        avg = rrow["avg"] if rrow else None
        cnt = rrow["c"] if rrow else 0
        avg_f = float(avg) if avg is not None else None
        out[sid] = _bundle_from_parts(
            verified=sid in verified_ids,
            avg_rating=avg_f,
            review_count=cnt,
            date_joined=user_dates.get(sid),
        )
    return out


def bulk_seller_trust(seller_ids):
    """
    Trust bundles for many sellers (cached per seller, TTL 5 min).
    Invalidated via invalidate_seller_trust_cache on review/verification changes.
    """
    seller_ids = {int(x) for x in seller_ids if x is not None}
    if not seller_ids:
        return {}

    out: dict = {}
    missing: set[int] = set()
    for sid in seller_ids:
        key = TRUST_CACHE_KEY.format(id=sid)
        hit = cache.get(key)
        if hit is not None:
            out[sid] = hit
        else:
            missing.add(sid)

    if missing:
        computed = _compute_bulk_seller_trust(missing)
        for sid, bundle in computed.items():
            cache.set(
                TRUST_CACHE_KEY.format(id=sid),
                bundle,
                TRUST_CACHE_TTL,
            )
            out[sid] = bundle

    return out


def seller_trust_bundle(user):
    """Single-seller trust summary for profile / detail / contact."""
    data = bulk_seller_trust([user.pk])
    return data.get(
        user.pk,
        _bundle_from_parts(
            verified=False,
            avg_rating=None,
            review_count=0,
            date_joined=user.date_joined,
        ),
    )


def sync_listing_flag(listing_id: int) -> None:
    """Set listing.is_flagged when report count reaches threshold (single UPDATE)."""
    from apps.listings.models import Listing

    n = ListingReport.objects.filter(listing_id=listing_id).count()
    Listing.objects.filter(pk=listing_id).update(is_flagged=(n >= 3))
