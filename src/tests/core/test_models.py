"""
Tests for core.models module.

These tests verify custom behavior of the Agent and Media models.
Only application-specific logic is tested here, not Django ORM basics.
"""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.models import MAX_FILE_SIZE_MB, Media, compress_image, dominant_color
from tests.helpers import image_bytes


@pytest.mark.parametrize(
    ("pub_year", "valid"), [(-4001, False), (-4000, True), (2024, True), (2200, True), (2201, False)]
)
def test_media_pub_year_is_between_4000_bc_and_2200(pub_year, valid):
    """Publication years are accepted from -4000 to 2200, both included."""
    media = Media(title="Work", media_type="BOOK", pub_year=pub_year)

    errors = {}
    try:
        media.clean_fields()
    except ValidationError as error:
        errors = error.message_dict

    assert ("pub_year" in errors) is not valid


def test_media_cover_image_compression(db):
    """Cover images are automatically compressed and resized when saved, keeping their aspect ratio."""
    cover = SimpleUploadedFile("test_cover.png", image_bytes((1920, 1080)), content_type="image/png")

    media = Media.objects.create(title="Test Media", media_type="BOOK", cover=cover)

    with Image.open(media.cover) as saved:
        assert saved.size == (800, 450)


def test_compress_image_file_size_validation():
    """Files exceeding MAX_FILE_SIZE_MB are rejected."""
    oversized_file = BytesIO()
    oversized_file.size = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024

    with pytest.raises(ValidationError, match="exceeds"):
        compress_image(oversized_file)


def test_compress_image_invalid_file():
    """Invalid or corrupted files are rejected."""
    with pytest.raises(ValidationError, match="Invalid or corrupted image file"):
        compress_image(BytesIO(b"This is not an image"))


def test_compress_image_unsupported_format():
    """Unsupported image formats are rejected."""
    with pytest.raises(ValidationError, match="Unsupported image format"):
        compress_image(BytesIO(image_bytes(fmt="TIFF")))


def test_compress_image_exif_orientation_preserved():
    """EXIF orientation metadata is correctly applied."""
    img = Image.new("RGB", (200, 100), color="green")
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation tag: rotate 90° clockwise
    img_io = BytesIO()
    img.save(img_io, format="JPEG", exif=exif)

    with Image.open(compress_image(img_io)) as result:
        assert result.size == (100, 200)


@pytest.mark.parametrize(
    ("mode", "color", "fmt"),
    [("RGB", "red", "JPEG"), ("RGB", "blue", "PNG"), ("RGBA", (255, 0, 0, 128), "PNG")],
)
def test_compress_image_turns_supported_images_into_rgb_jpeg(mode, color, fmt):
    """Supported images, transparent ones included, are compressed to RGB JPEG within 800 pixels."""
    compressed = compress_image(BytesIO(image_bytes((1000, 1000), color=color, fmt=fmt, mode=mode)))

    with Image.open(compressed) as result:
        assert (result.format, result.mode) == ("JPEG", "RGB")
        assert result.size == (800, 800)


def test_dominant_color_is_the_most_common_colour():
    """The dominant colour of an image is the one covering most of it, as a hex string."""
    img = Image.new("RGB", (100, 100), color="#333333")
    img.paste((0, 0, 255), (0, 0, 40, 40))
    img_io = BytesIO()
    img.save(img_io, format="PNG")

    assert dominant_color(img_io) == "#333333"


def test_dominant_color_of_an_unreadable_file_is_empty():
    """A file that is not an image has no dominant colour."""
    assert dominant_color(BytesIO(b"not an image")) == ""


def test_media_uploaded_cover_is_a_jpeg_keeping_its_colour(db, cover_png):
    """An uploaded cover, compressed to JPEG whatever its format, gets the matching extension and keeps its colour."""
    media = Media.objects.create(title="Test", media_type="BOOK", cover=SimpleUploadedFile("cover.png", cover_png))

    assert media.cover.name == "covers/cover.jpg"
    assert media.cover_color == "#333333"


def test_media_cover_color_cleared_with_its_cover(media_factory):
    """Removing the cover of a media clears its colour."""
    media = media_factory(cover="covers/cover.jpg", cover_color="#333333")
    media.cover = None
    media.save()

    assert media.cover_color == ""


def test_saved_view_str_representation(user, saved_view_factory):
    """The string representation includes username and view name."""
    assert str(saved_view_factory(name="My Favorite Books")) == f"{user.username} - My Favorite Books"


def test_get_filter_url_with_defaults(saved_view_factory):
    """A saved view without filters leads to the list with the default sort."""
    assert saved_view_factory().get_filter_url() == "/?sort=-review_date"


def test_get_filter_url_holds_every_set_filter(saved_view_factory):
    """A saved view leads to the list with each of its filters, the multi-valued ones repeated."""
    saved_view = saved_view_factory(
        filter_types=["BOOK", "FILM"],
        filter_statuses=["COMPLETED"],
        filter_scores=["9", "10"],
        filter_contributor_id=42,
        filter_tag_id=7,
        filter_review_from="2024-01",
        filter_review_to="2024-12",
        filter_has_review="filled",
        filter_has_cover="empty",
        sort="-score",
    )

    assert saved_view.get_filter_url() == (
        "/?type=BOOK&type=FILM&status=COMPLETED&score=9&score=10&contributor=42&tag=7"
        "&review_from=2024-01&review_to=2024-12&has_review=filled&has_cover=empty&sort=-score"
    )
