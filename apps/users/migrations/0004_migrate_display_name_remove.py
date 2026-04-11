from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    for u in User.objects.all().only("id", "display_name", "first_name", "last_name"):
        dn = (getattr(u, "display_name", "") or "").strip()
        if not dn:
            continue
        # Only backfill if names are empty.
        if (u.first_name or "").strip() or (u.last_name or "").strip():
            continue
        parts = dn.split()
        u.first_name = parts[0] if parts else ""
        u.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        u.save(update_fields=["first_name", "last_name"])


def backwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    for u in User.objects.all().only("id", "first_name", "last_name"):
        full = f"{(u.first_name or '').strip()} {(u.last_name or '').strip()}".strip()
        if not full:
            continue
        u.display_name = full
        u.save(update_fields=["display_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_userverification"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name="user", name="display_name"),
    ]

