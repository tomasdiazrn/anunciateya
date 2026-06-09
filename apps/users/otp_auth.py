from dataclasses import dataclass
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.core.emails import send_user_otp_email

from .models import UserLoginOTP


@dataclass(frozen=True)
class OTPRequestResult:
    email: str
    user_id: int | None = None
    sent: bool = False
    reason: str = "invalid_user"


@dataclass(frozen=True)
class OTPVerifyResult:
    success: bool
    user: object | None = None
    reason: str = "invalid_code"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def generate_user_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def find_valid_login_user(email: str):
    normalized = normalize_email(email)
    if not normalized:
        return None
    UserModel = get_user_model()
    return UserModel.objects.filter(
        email__iexact=normalized,
        is_active=True,
    ).first()


def _active_otps(user, email, now):
    return UserLoginOTP.objects.filter(
        user=user,
        email=email,
        used_at__isnull=True,
        expires_at__gt=now,
    )


def request_user_otp(email: str) -> OTPRequestResult:
    normalized = normalize_email(email)
    user = find_valid_login_user(normalized)
    if user is None:
        return OTPRequestResult(email=normalized)

    now = timezone.now()
    exhausted_since = now - timezone.timedelta(
        minutes=settings.USER_OTP_ATTEMPT_COOLDOWN_MINUTES
    )
    if UserLoginOTP.objects.filter(
        user=user,
        email=normalized,
        attempts__gte=settings.USER_OTP_MAX_ATTEMPTS,
        used_at__gte=exhausted_since,
    ).exists():
        return OTPRequestResult(
            email=normalized,
            user_id=user.pk,
            reason="attempt_cooldown",
        )

    resend_since = now - timezone.timedelta(seconds=settings.USER_OTP_RESEND_COOLDOWN_SECONDS)
    if UserLoginOTP.objects.filter(
        user=user,
        email=normalized,
        created_at__gte=resend_since,
    ).exists():
        return OTPRequestResult(
            email=normalized,
            user_id=user.pk,
            reason="resend_cooldown",
        )

    send_window_since = now - timezone.timedelta(minutes=settings.USER_OTP_SEND_WINDOW_MINUTES)
    if (
        UserLoginOTP.objects.filter(
            user=user,
            email=normalized,
            created_at__gte=send_window_since,
        ).count()
        >= settings.USER_OTP_SEND_LIMIT
    ):
        return OTPRequestResult(
            email=normalized,
            user_id=user.pk,
            reason="send_limit",
        )

    code = generate_user_otp_code()
    expires_at = now + timezone.timedelta(minutes=settings.USER_OTP_EXPIRY_MINUTES)
    with transaction.atomic():
        _active_otps(user, normalized, now).update(used_at=now)
        UserLoginOTP.objects.create(
            user=user,
            email=normalized,
            code_hash=make_password(code),
            expires_at=expires_at,
            max_attempts=settings.USER_OTP_MAX_ATTEMPTS,
        )

    if settings.DEBUG:
        print(f"[USER OTP LOGIN]\nEmail: {normalized}\nCode: {code}")

    send_user_otp_email(normalized, code, settings.USER_OTP_EXPIRY_MINUTES)
    return OTPRequestResult(email=normalized, user_id=user.pk, sent=True, reason="sent")


def verify_user_otp(user_id, email: str, code: str) -> OTPVerifyResult:
    normalized = normalize_email(email)
    raw_code = (code or "").strip()
    if not user_id or not normalized or not raw_code:
        return OTPVerifyResult(success=False)

    user = find_valid_login_user(normalized)
    if user is None or str(user.pk) != str(user_id):
        return OTPVerifyResult(success=False)

    now = timezone.now()
    with transaction.atomic():
        otp = (
            UserLoginOTP.objects.select_for_update()
            .filter(user=user, email=normalized, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            return OTPVerifyResult(success=False)
        if otp.expires_at <= now:
            otp.used_at = now
            otp.save(update_fields=["used_at"])
            return OTPVerifyResult(success=False, reason="expired")
        if otp.attempts >= otp.max_attempts:
            otp.used_at = now
            otp.save(update_fields=["used_at"])
            return OTPVerifyResult(success=False, reason="max_attempts")
        if check_password(raw_code, otp.code_hash):
            otp.used_at = now
            otp.save(update_fields=["used_at"])
            return OTPVerifyResult(success=True, user=user, reason="verified")

        otp.attempts += 1
        update_fields = ["attempts"]
        reason = "invalid_code"
        if otp.attempts >= otp.max_attempts:
            otp.used_at = now
            update_fields.append("used_at")
            reason = "max_attempts"
        otp.save(update_fields=update_fields)
        return OTPVerifyResult(success=False, reason=reason)
