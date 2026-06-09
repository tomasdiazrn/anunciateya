from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

HOSTING_MEMBERSHIP_WARNING_DAYS = 30
HOSTING_MEMBERSHIP_POPUP_DAYS = 7

STATUS_NOT_CONFIGURED = "not_configured"
STATUS_ACTIVE = "active"
STATUS_EXPIRING = "expiring"
STATUS_EXPIRED = "expired"


@dataclass(frozen=True)
class HostingMembership:
    start_date: date | None
    expires_date: date | None
    days_remaining: int | None
    status: str
    is_configured: bool
    config_error: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def is_expiring(self) -> bool:
        return self.status == STATUS_EXPIRING

    @property
    def is_expired(self) -> bool:
        return self.status == STATUS_EXPIRED

    @property
    def show_alert(self) -> bool:
        return self.status in {STATUS_EXPIRING, STATUS_EXPIRED}

    @property
    def absolute_days_remaining(self) -> int | None:
        if self.days_remaining is None:
            return None
        return abs(self.days_remaining)


def _parse_date(raw_value: str) -> date | None:
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        return None


def get_hosting_membership(today: date | None = None) -> HostingMembership:
    start_raw = getattr(settings, "HOSTING_MEMBERSHIP_START_DATE", "")
    expires_raw = getattr(settings, "HOSTING_MEMBERSHIP_EXPIRES_DATE", "")
    start_date = _parse_date(start_raw)
    expires_date = _parse_date(expires_raw)

    if not start_date or not expires_date:
        config_error = ""
        if start_raw or expires_raw:
            config_error = "Revisá que las fechas estén en formato YYYY-MM-DD."
        return HostingMembership(
            start_date=start_date,
            expires_date=expires_date,
            days_remaining=None,
            status=STATUS_NOT_CONFIGURED,
            is_configured=False,
            config_error=config_error,
        )

    current_date = today or timezone.localdate()
    days_remaining = (expires_date - current_date).days
    if days_remaining < 0:
        status = STATUS_EXPIRED
    elif days_remaining <= HOSTING_MEMBERSHIP_WARNING_DAYS:
        status = STATUS_EXPIRING
    else:
        status = STATUS_ACTIVE

    return HostingMembership(
        start_date=start_date,
        expires_date=expires_date,
        days_remaining=days_remaining,
        status=status,
        is_configured=True,
    )


def build_renewal_url(request) -> str:
    base_url = (
        getattr(settings, "HOSTING_RENEWAL_URL", "")
        or "https://altovalleit.com/hosting/"
    ).strip()
    user = getattr(request, "user", None)
    site_name = getattr(settings, "SITE_NAME", "") or getattr(
        settings,
        "PUBLIC_SITE_DOMAIN",
        "",
    )

    params = {
        "utm_source": "anunciateya_admin",
        "utm_medium": "hosting_tab",
        "utm_campaign": "hosting_renewal",
        "site_name": site_name,
    }
    if user and getattr(user, "is_authenticated", False):
        params.update(
            {
                "user_id": str(user.pk),
                "user_email": getattr(user, "email", "") or "",
                "username": getattr(user, "public_name", "")
                or getattr(user, "email", ""),
            }
        )

    split = urlsplit(base_url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update({key: value for key, value in params.items() if value})
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
    )
