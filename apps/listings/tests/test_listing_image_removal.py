from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict
from PIL import Image

from apps.categories.models import Category
from apps.listings.models import Listing, ListingImage
from apps.listings.services import (
    commit_listing_image_changes,
    parse_remove_image_ids,
    remove_listing_images,
    resolve_listing_image_removals,
    validate_listing_image_changes,
)

User = get_user_model()


def _png_upload(name: str = "foto.png") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (8, 8), (120, 120, 120)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class _DummyForm:
    def __init__(self):
        self.errors = {}

    def add_error(self, field, message):
        self.errors[field or "__all__"] = message

    def is_valid(self):
        return True


class ListingImageRemovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            email="image-removal-seller@example.com",
            password="test-pass-123",
        )
        cls.category, _ = Category.objects.get_or_create(
            slug="hogar",
            defaults={"name": "Hogar", "order": 0},
        )

    def _listing(self) -> Listing:
        return Listing.objects.create(
            title="Mesa usada",
            description="Mesa en buen estado.",
            price_amount="80.00",
            currency="USD",
            location="Guayaquil",
            seller=self.seller,
            category=self.category,
            status=Listing.Status.PUBLISHED,
        )

    def _create_image(self, listing: Listing, *, sort_order: int = 0) -> ListingImage:
        return ListingImage.objects.create(
            listing=listing,
            image=_png_upload(f"foto-{sort_order}.png"),
            sort_order=sort_order,
        )

    def test_parse_remove_image_ids_deduplicates(self):
        class Post:
            def getlist(self, key):
                if key == "remove_images":
                    return ["3", "3", "7", "x"]
                return []

        self.assertEqual(parse_remove_image_ids(Post()), [3, 7])

    def test_resolve_listing_image_removals_ignores_foreign_ids(self):
        listing = self._listing()
        other = self._listing()
        keep = self._create_image(listing, sort_order=0)
        foreign = self._create_image(other, sort_order=0)

        resolved = resolve_listing_image_removals(
            listing,
            [keep.pk, foreign.pk, 99999],
        )

        self.assertEqual(resolved, [keep.pk])

    def test_remove_listing_images_deletes_db_rows_and_files(self):
        listing = self._listing()
        first = self._create_image(listing, sort_order=0)
        second = self._create_image(listing, sort_order=1)
        first_path = first.image.name
        second_path = second.image.name
        self.assertTrue(default_storage.exists(first_path))
        self.assertTrue(default_storage.exists(second_path))

        removed = remove_listing_images(listing, [first.pk])

        self.assertEqual(removed, 1)
        self.assertFalse(ListingImage.objects.filter(pk=first.pk).exists())
        self.assertTrue(ListingImage.objects.filter(pk=second.pk).exists())
        self.assertFalse(default_storage.exists(first_path))
        self.assertTrue(default_storage.exists(second_path))

    def test_validate_listing_image_changes_respects_remaining_slots(self):
        listing = self._listing()
        self._create_image(listing, sort_order=0)
        self._create_image(listing, sort_order=1)
        form = _DummyForm()

        uploads = [_png_upload("nueva-1.png"), _png_upload("nueva-2.png")]
        remove_id = str(listing.images.order_by("id").first().pk)

        class Post:
            POST = MultiValueDict({"remove_images": [remove_id]})
            FILES = MultiValueDict({"images": uploads})

        ok = validate_listing_image_changes(Post(), listing, form)

        self.assertTrue(ok)
        self.assertFalse(form.errors)

    def test_commit_listing_image_changes_removes_marked_and_attaches_new(self):
        listing = self._listing()
        old = self._create_image(listing, sort_order=0)

        upload = _png_upload("nueva.png")

        class Post:
            POST = MultiValueDict({"remove_images": [str(old.pk)]})
            FILES = MultiValueDict({"images": [upload]})

        commit_listing_image_changes(Post(), listing)

        self.assertFalse(ListingImage.objects.filter(pk=old.pk).exists())
        self.assertEqual(listing.images.count(), 1)
        self.assertTrue(listing.images.first().image.name.endswith(".png"))
