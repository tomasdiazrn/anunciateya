"""Production middleware for the public marketplace."""


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
