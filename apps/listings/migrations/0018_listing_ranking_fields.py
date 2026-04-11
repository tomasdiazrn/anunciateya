from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0017_home_contract_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="featured_until",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="listing",
            name="boost_score",
            field=models.IntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="listing",
            name="quality_score",
            field=models.FloatField(db_index=True, default=0.0),
        ),
    ]
