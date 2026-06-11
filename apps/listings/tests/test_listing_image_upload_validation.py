from io import BytesIO
from types import SimpleNamespace

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict
from PIL import Image

from apps.listings.services import validate_listing_image_uploads


class _UploadValidationForm(forms.Form):
    pass


class ListingImageUploadValidationTests(TestCase):
    def _request_with_files(self, files):
        return SimpleNamespace(FILES=MultiValueDict({"images": files}))

    def _png_bytes(self):
        buf = BytesIO()
        Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
        return buf.getvalue()

    def test_accepts_valid_png_upload(self):
        form = _UploadValidationForm(data={})
        form.is_valid()
        upload = SimpleUploadedFile("foto.png", self._png_bytes(), content_type="image/png")

        ok = validate_listing_image_uploads(self._request_with_files([upload]), form)

        self.assertTrue(ok)
        self.assertFalse(form.errors)

    def test_rejects_corrupt_file_even_with_image_extension(self):
        form = _UploadValidationForm(data={})
        form.is_valid()
        upload = SimpleUploadedFile(
            "foto.jpg",
            b"not a real image",
            content_type="image/jpeg",
        )

        ok = validate_listing_image_uploads(self._request_with_files([upload]), form)

        self.assertFalse(ok)
        self.assertIn("No pudimos leer", str(form.non_field_errors()))

    def test_rejects_unsupported_extension(self):
        form = _UploadValidationForm(data={})
        form.is_valid()
        upload = SimpleUploadedFile("foto.gif", b"GIF89a", content_type="image/gif")

        ok = validate_listing_image_uploads(self._request_with_files([upload]), form)

        self.assertFalse(ok)
        self.assertIn("Formato no soportado", str(form.non_field_errors()))
