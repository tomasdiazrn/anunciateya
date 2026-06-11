from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.urls import reverse


USER_NAME_MAX_LENGTH = 25
USER_EMAIL_MAX_LENGTH = 255


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Email-first user; username field removed per Django custom user docs."""

    username = None
    first_name = models.CharField(
        "first name",
        max_length=USER_NAME_MAX_LENGTH,
        blank=True,
    )
    last_name = models.CharField(
        "last name",
        max_length=USER_NAME_MAX_LENGTH,
        blank=True,
    )
    email = models.EmailField(
        "email address",
        max_length=USER_EMAIL_MAX_LENGTH,
        unique=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["date_joined"]),
        ]

    def __str__(self):
        return self.public_name

    @property
    def public_name(self) -> str:
        full = f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip()
        return full or self.email

    def get_absolute_url(self):
        return reverse("users:profile", kwargs={"pk": self.pk})


class UserVerification(models.Model):
    """Phone verification state (SMS integration can replace simulated flow later)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification",
    )
    phone_country_code = models.CharField(max_length=8, blank=True, default="+593")
    phone_number = models.CharField(max_length=32, blank=True)
    phone_verified = models.BooleanField(default=False, db_index=True)
    whatsapp_contact_enabled = models.BooleanField(default=False)
    show_name_in_listings = models.BooleanField(default=True)
    verification_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone_verified"]),
        ]

    def __str__(self):
        return f"Verification for {self.user_id}"


class UserLoginOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_otps",
    )
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "email", "used_at"]),
            models.Index(fields=["email", "created_at"]),
        ]

    def __str__(self):
        return f"Login OTP for {self.email} at {self.created_at:%Y-%m-%d %H:%M:%S}"
