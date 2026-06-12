from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse


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
    logo_url = (
        logo_path if logo_path.startswith(("http://", "https://")) else static(logo_path)
    )

    return {
        "site_name": getattr(settings, "SITE_NAME", "AnunciateYa"),
        "seo_brand_name": getattr(settings, "SEO_BRAND_NAME", "AnunciateYa"),
        "site_url": getattr(settings, "PUBLIC_SITE_URL", "").rstrip("/"),
        "site_public_domain": getattr(settings, "PUBLIC_SITE_DOMAIN", ""),
        "brand_logo_url": _absolute_url(logo_url),
        "brand_theme_color": getattr(settings, "BRAND_THEME_COLOR", "#3CBB6B"),
        "contact_email": getattr(settings, "CONTACT_EMAIL", ""),
    }


def _branded_from_email(brand_context):
    _, email_address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    from_name = getattr(
        settings,
        "EMAIL_FROM_NAME",
        brand_context["seo_brand_name"],
    )
    return formataddr((from_name, email_address or settings.DEFAULT_FROM_EMAIL))


def _send_branded_email(subject, text_template, html_template, context, recipient_email):
    email_context = _email_brand_context() | context
    text_body = render_to_string(text_template, email_context)
    html_body = render_to_string(html_template, email_context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=_branded_from_email(email_context),
        to=[recipient_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()


def send_user_otp_email(recipient_email, code, expires_in_minutes):
    brand_context = _email_brand_context()
    context = {
        "code": code,
        "expires_in_minutes": expires_in_minutes,
    }
    subject = (
        f"Tu código de {brand_context['seo_brand_name']} "
        f"vence en {expires_in_minutes} min"
    )
    _send_branded_email(
        subject,
        "emails/user_otp.txt",
        "emails/user_otp.html",
        context,
        recipient_email,
    )


def send_listing_interest_email(listing, buyer_name, buyer_email, message):
    account_leads_url = _absolute_url(reverse("users:account_leads"))
    context = {
        "listing_title": listing.title,
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "message": message,
        "account_leads_url": account_leads_url,
    }
    subject = f"Te escribieron por tu anuncio: {listing.title}"
    _send_branded_email(
        subject,
        "emails/listing_interest.txt",
        "emails/listing_interest.html",
        context,
        listing.seller.email,
    )
