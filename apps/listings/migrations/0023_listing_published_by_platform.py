from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0022_remove_listing_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="published_by_platform",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Marks listings created by staff on behalf of the marketplace.",
            ),
        ),
    ]
