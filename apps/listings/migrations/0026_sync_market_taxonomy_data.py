from __future__ import annotations

from django.core.management import call_command
from django.db import migrations


def sync_market_taxonomy(apps, schema_editor):
    call_command("sync_market_taxonomy")


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0025_market_taxonomy_fk_required"),
    ]

    operations = [
        migrations.RunPython(sync_market_taxonomy, migrations.RunPython.noop),
    ]
