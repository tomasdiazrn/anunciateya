from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("adminapp", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AdminLoginOTP",
        ),
    ]
