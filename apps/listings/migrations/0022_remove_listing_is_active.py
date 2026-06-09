from django.db import migrations, models


def archive_inactive_published_listings(apps, schema_editor):
    Listing = apps.get_model("listings", "Listing")
    Listing.objects.filter(is_active=False, status="published").update(
        status="archived"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0021_listingimage_image_large_webp_and_more"),
    ]

    operations = [
        migrations.RunPython(
            archive_inactive_published_listings,
            migrations.RunPython.noop,
        ),
        migrations.RemoveIndex(
            model_name="listing",
            name="listings_li_status_a0549e_idx",
        ),
        migrations.RemoveField(
            model_name="listing",
            name="is_active",
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(
                fields=["status", "-created_at"],
                name="listing_status_created_idx",
            ),
        ),
    ]
