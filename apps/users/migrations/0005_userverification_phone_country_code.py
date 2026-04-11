import re

from django.db import migrations, models


def forwards(apps, schema_editor):
    UserVerification = apps.get_model("users", "UserVerification")
    for v in UserVerification.objects.all().only("id", "phone_number", "phone_country_code"):
        raw = (v.phone_number or "").strip()
        if not raw:
            continue

        # Attempt to parse formats like "+593 987654321" into parts.
        m = re.match(r"^\s*(\+\d{1,4})\s*(.*)$", raw)
        if m:
            code = m.group(1)
            rest = m.group(2) or ""
            digits = re.sub(r"\D", "", rest)
            v.phone_country_code = code
            v.phone_number = digits
            v.save(update_fields=["phone_country_code", "phone_number"])
            continue

        # Otherwise, keep only digits in phone_number.
        digits = re.sub(r"\D", "", raw)
        if digits != raw:
            v.phone_number = digits
            v.save(update_fields=["phone_number"])


def backwards(apps, schema_editor):
    UserVerification = apps.get_model("users", "UserVerification")
    for v in UserVerification.objects.all().only("id", "phone_number", "phone_country_code"):
        digits = re.sub(r"\D", "", v.phone_number or "")
        code = (v.phone_country_code or "").strip()
        if not digits:
            continue
        if code and code.startswith("+"):
            v.phone_number = f"{code} {digits}"
            v.save(update_fields=["phone_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_migrate_display_name_remove"),
    ]

    operations = [
        migrations.AddField(
            model_name="userverification",
            name="phone_country_code",
            field=models.CharField(blank=True, default="+593", max_length=8),
        ),
        migrations.RunPython(forwards, backwards),
    ]

