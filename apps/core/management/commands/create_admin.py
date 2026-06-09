from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update an OTP-only admin user."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Admin email address.")

    def handle(self, *args, **options):
        raw_email = (options["email"] or "").strip().lower()
        if not raw_email:
            raise CommandError("--email is required.")

        UserModel = get_user_model()
        email = UserModel.objects.normalize_email(raw_email).lower()
        user, created = UserModel.objects.get_or_create(email=email)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_unusable_password()
        user.save(
            update_fields=[
                "is_staff",
                "is_superuser",
                "is_active",
                "password",
            ]
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} OTP-only admin: {email}"))
