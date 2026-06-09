"""
Listing images pipeline (Pillow).

Design goals:
- Keep the original upload untouched (ListingImage.image).
- Generate optimized variants into optional fields:
  - thumb  : 400x400 (center crop) for cards
  - medium : 800x600 (contain + pad) for detail gallery
  - large  : max width 1200 (preserve ratio) for fullscreen

Callers must treat this as best-effort and never break the upload flow.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from django.core.files.base import ContentFile

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ImageVariant:
    name: str
    ext: str
    content: ContentFile


def _ensure_pillow() -> None:
    if Image is None or ImageOps is None:  # pragma: no cover
        raise RuntimeError("Pillow is required for image processing.")


def _to_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode == "RGB":
        return im
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        return bg
    return im.convert("RGB")


def _save_jpeg(im: Image.Image, *, quality: int = 82) -> ContentFile:
    buf = io.BytesIO()
    im.save(
        buf,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return ContentFile(buf.getvalue())


def _save_webp(im: Image.Image, *, quality: int = 78) -> ContentFile:
    buf = io.BytesIO()
    im.save(
        buf,
        format="WEBP",
        quality=quality,
        method=6,
    )
    return ContentFile(buf.getvalue())


def _thumb_400(im: Image.Image) -> Image.Image:
    return ImageOps.fit(im, (400, 400), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _medium_800x600(im: Image.Image) -> Image.Image:
    target = (800, 600)
    contained = ImageOps.contain(im, target, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", target, (248, 250, 252))
    x = (target[0] - contained.size[0]) // 2
    y = (target[1] - contained.size[1]) // 2
    canvas.paste(contained, (x, y))
    return canvas


def _large_max1200(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w <= 1200:
        return im
    new_h = int(round(h * (1200 / float(w))))
    return im.resize((1200, max(1, new_h)), resample=Image.Resampling.LANCZOS)


def generate_listing_image_variants(uploaded_file, *, quality: int = 82) -> dict[str, ImageVariant]:
    _ensure_pillow()
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as im0:
        im = _to_rgb(im0)
        thumb = _thumb_400(im)
        medium = _medium_800x600(im)
        large = _large_max1200(im)

    # JPEG base + WebP (lighter) variants.
    return {
        "thumb": ImageVariant("thumb", "jpg", _save_jpeg(thumb, quality=quality)),
        "thumb_webp": ImageVariant("thumb", "webp", _save_webp(thumb, quality=78)),
        "medium": ImageVariant("medium", "jpg", _save_jpeg(medium, quality=quality)),
        "medium_webp": ImageVariant("medium", "webp", _save_webp(medium, quality=78)),
        "large": ImageVariant("large", "jpg", _save_jpeg(large, quality=quality)),
        "large_webp": ImageVariant("large", "webp", _save_webp(large, quality=78)),
    }

