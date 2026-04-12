"""Pre-launch hardening: landing-only access and Content-Security-Policy."""

from django.conf import settings
from django.http import Http404


class LandingOnlyMiddleware:
    """
    When LANDING_ONLY_ENABLED is True: allow only GET/HEAD/OPTIONS/POST on
    /proximamente/, GET /health/, and static/media URL prefixes. Everything else → 404.
    """

    _landing_paths = frozenset({"/", "/proximamente", "/proximamente/"})
    _health_path = "/health/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "LANDING_ONLY_ENABLED", False):
            return self.get_response(request)

        path = request.path

        if path == self._health_path and request.method == "GET":
            return self.get_response(request)

        static_url = settings.STATIC_URL
        if not static_url.startswith("/"):
            static_url = "/" + static_url
        media_url = settings.MEDIA_URL
        if not media_url.startswith("/"):
            media_url = "/" + media_url

        if path.startswith(static_url) or path.startswith(media_url):
            return self.get_response(request)

        if path in self._landing_paths and request.method in (
            "GET",
            "HEAD",
            "OPTIONS",
            "POST",
        ):
            return self.get_response(request)

        raise Http404()


class ContentSecurityPolicyMiddleware:
    """Append a strict-but-practical CSP for the pre-launch stack (GTM, Pixel, CDNs, inline bootstraps)."""

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
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:",
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
