"""User domain helpers (verification, onboarding)."""


def is_phone_verified(user) -> bool:
    if not user.is_authenticated:
        return False
    v = getattr(user, "verification", None)
    return bool(v and v.phone_verified)
