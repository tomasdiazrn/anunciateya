from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_alter_user_email_alter_user_first_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userverification",
            name="whatsapp_contact_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
