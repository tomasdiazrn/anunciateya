from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_userverification_whatsapp_contact_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="userverification",
            name="show_name_in_listings",
            field=models.BooleanField(default=True),
        ),
    ]
