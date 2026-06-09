from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.templatetags.static import static


def _absolute_url(path):
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path

    site_url = getattr(settings, "PUBLIC_SITE_URL", "").rstrip("/")
    if not site_url:
        return path

    separator = "" if path.startswith("/") else "/"
    return f"{site_url}{separator}{path}"


def _email_brand_context():
    logo_path = getattr(settings, "BRAND_LOGO_PATH", "img/AnunciateYa_Logo.png")
    logo_url = logo_path if logo_path.startswith(("http://", "https://")) else static(logo_path)

    return {
        "site_name": getattr(settings, "SITE_NAME", "AnunciateYa"),
        "seo_brand_name": getattr(settings, "SEO_BRAND_NAME", "AnunciateYa"),
        "site_url": getattr(settings, "PUBLIC_SITE_URL", "").rstrip("/"),
        "site_public_domain": getattr(settings, "PUBLIC_SITE_DOMAIN", ""),
        "brand_logo_url": _absolute_url(logo_url),
        "brand_theme_color": getattr(settings, "BRAND_THEME_COLOR", "#3CBB6B"),
        "contact_email": getattr(settings, "CONTACT_EMAIL", ""),
    }


def send_user_otp_email(recipient_email, code, expires_in_minutes):
    context = _email_brand_context() | {
        "code": code,
        "expires_in_minutes": expires_in_minutes,
    }
    subject = f"Tu código para ingresar a {context['seo_brand_name']}"
    text_body = render_to_string("emails/user_otp.txt", context)
    html_body = render_to_string("emails/user_otp.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
