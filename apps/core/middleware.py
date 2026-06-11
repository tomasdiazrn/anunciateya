"""Production middleware for the public marketplace."""

from django_htmx.http import HttpResponseClientRedirect

_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


class HtmxClientRedirectMiddleware:
    """Turn HTTP redirects into full-page navigations for HTMX requests.

    Without this, HTMX follows 3xx responses and swaps the target HTML into the
    request's hx-target (e.g. login markup inside the account dashboard shell).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(request, "htmx", False):
            return response
        if response.status_code not in _REDIRECT_STATUS_CODES:
            return response
        location = response.get("Location")
        if not location:
            return response
        return HttpResponseClientRedirect(location)


class ContentSecurityPolicyMiddleware:
    """Append a strict-but-practical CSP for GTM, Pixel, CDNs, and inline bootstraps."""

    _policy_parts = (
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
        "frame-src https://www.googletagmanager.com",
        # GA4 + GTM (Google): subdominios de recogida; ver
        # https://developers.google.com/tag-platform/security/guides/csp
        "script-src 'self' 'unsafe-inline' https://*.googletagmanager.com "
        "https://connect.facebook.net https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://api.fontshare.com "
        "https://cdnjs.cloudflare.com",
        "font-src 'self' https://fonts.gstatic.com https://cdn.fontshare.com "
        "https://cdnjs.cloudflare.com data:",
        "img-src 'self' data: https: https://*.google-analytics.com https://*.googletagmanager.com",
        "connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com "
        "https://*.googletagmanager.com https://www.google.com "
        "https://www.facebook.com https://connect.facebook.net",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self._value = "; ".join(self._policy_parts)

    def __call__(self, request):
        response = self.get_response(request)
        if response.has_header("Content-Security-Policy"):
            return response
        response["Content-Security-Policy"] = self._value
        return response
