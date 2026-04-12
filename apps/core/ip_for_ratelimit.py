"""Cliente IP estable para django-ratelimit detrás de proxy / CDN."""

from __future__ import annotations

import ipaddress
from typing import Optional


def _parse_first_ip(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip().split(",")[0].strip()
    if not s:
        return None
    if s.startswith("[") and "]" in s:
        s = s.split("]", 1)[0][1:]
    if s.count(":") == 1 and "." in s:
        s = s.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(s)
    except ValueError:
        return None
    return s


def client_ip_for_ratelimit(request):
    """
    Orden: cabeceras habituales de CDN/proxy, luego REMOTE_ADDR.
    Si nada es parseable, 127.0.0.1 evita ImproperlyConfigured / ValueError en django-ratelimit.
    """
    for key in (
        "HTTP_CF_CONNECTING_IP",
        "HTTP_X_REAL_IP",
        "HTTP_X_FORWARDED_FOR",
    ):
        parsed = _parse_first_ip(request.META.get(key) or "")
        if parsed:
            return parsed
    parsed = _parse_first_ip(request.META.get("REMOTE_ADDR") or "")
    if parsed:
        return parsed
    return "127.0.0.1"
