from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trust", "0006_listingreport_reviewed_at_listingreport_reviewed_by_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS trust_review;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
