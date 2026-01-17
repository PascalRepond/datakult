"""
Tests for core.models module.

These tests verify custom behavior of the Agent and Media models.
Only application-specific logic is tested here, not Django ORM basics.
"""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from freezegun import freeze_time
from PIL import Image

from core.models import MAX_FILE_SIZE_MB, Media, SavedView, compress_image


class TestAgentModel:
    """Tests for the Agent model."""

    def test_agent_str_representation(self, agent):
        """The string representation of an agent is its name."""
        assert str(agent) == agent.name

    def test_agent_updated_at_auto_updates_on_save(self, agent, db):
        """The updated_at field is automatically updated when agent is saved."""
        # Freeze time at a specific moment
        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # Create/update agent at this frozen time
            agent.name = "Initial Name"
            agent.save()
            agent.refresh_from_db()
            original_updated_at = agent.updated_at

            # Move time forward by 1 hour
            frozen_time.move_to("2024-01-01 13:00:00")

            # Update and save again
            agent.name = "Updated Name"
            agent.save()

            # Refresh from database
            agent.refresh_from_db()

            # updated_at should be more recent than original
            assert agent.updated_at > original_updated_at


class TestMediaModel:
    """Tests for the Media model."""

    def test_media_str_representation(self, media):
        """The string representation of a media is its title."""
        assert str(media) == media.title

    def test_media_pub_year_validation_too_early(self, db):
        """Publication year before -4000 is rejected."""
        media = Media(
            title="Ancient Work",
            media_type="BOOK",
            pub_year=-5000,
        )

        with pytest.raises(ValidationError) as exc_info:
            media.full_clean()
        assert "pub_year" in exc_info.value.message_dict

    def test_media_pub_year_validation_too_late(self, db):
        """Publication year after 2200 is rejected."""
        media = Media(
            title="Future Work",
            media_type="BOOK",
            pub_year=2500,
        )

        with pytest.raises(ValidationError) as exc_info:
            media.full_clean()
        assert "pub_year" in exc_info.value.message_dict

    def test_media_pub_year_validation_valid_range(self, db):
        """Publication year within valid range is accepted."""
        media = Media(
            title="Normal Work",
            media_type="BOOK",
            pub_year=2024,
        )
        # Should not raise
        media.full_clean()

    def test_media_cover_image_compression(self, db):
        """Cover images are automatically compressed and resized when saved."""
        # Create a large test image (1920x1080)
        img = Image.new("RGB", (1920, 1080), color="red")
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)

        # Create a Media object with the large image
        cover_file = SimpleUploadedFile("test_cover.png", img_io.read(), content_type="image/png")
        media = Media(
            title="Test Media",
            media_type="BOOK",
            cover=cover_file,
        )
        media.save()

        # Verify the image was saved
        assert media.cover
        assert media.cover.name

        # Open the saved image and check dimensions
        saved_image = Image.open(media.cover)
        width, height = saved_image.size

        # Image should be resized to fit within 800x800
        assert width <= 800
        assert height <= 800

        # Aspect ratio should be preserved (1920:1080 = 16:9)
        # The image should be 800x450 (preserving 16:9 ratio)
        assert width == 800
        assert height == 450

        # Cleanup
        media.cover.delete(save=False)
        media.delete()

    def test_media_updated_at_auto_updates_on_save(self, media, db):
        """The updated_at field is automatically updated when media is saved."""
        # Freeze time at a specific moment
        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # Create/update media at this frozen time
            media.title = "Initial Title"
            media.save()
            media.refresh_from_db()
            original_updated_at = media.updated_at

            # Move time forward by 1 hour
            frozen_time.move_to("2024-01-01 13:00:00")

            # Update and save again
            media.title = "Updated Title"
            media.save()

            # Refresh from database
            media.refresh_from_db()

            # updated_at should be more recent than original
            assert media.updated_at > original_updated_at


class TestCompressImageSecurity:
    """Tests for security features of the compress_image function."""

    def test_compress_image_file_size_validation(self):
        """Files exceeding MAX_FILE_SIZE_MB are rejected."""
        # Create a mock file object with size exceeding the limit
        oversized_file = BytesIO()
        oversized_file.size = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024

        with pytest.raises(ValidationError) as exc_info:
            compress_image(oversized_file)
        assert "exceeds" in str(exc_info.value).lower()

    def test_compress_image_invalid_file(self):
        """Invalid or corrupted files are rejected."""
        invalid_file = BytesIO(b"This is not an image")

        with pytest.raises(ValidationError) as exc_info:
            compress_image(invalid_file)
        assert "invalid" in str(exc_info.value).lower() or "corrupted" in str(exc_info.value).lower()

    def test_compress_image_unsupported_format(self):
        """Unsupported image formats are rejected."""
        # Create a TIFF image (not in ALLOWED_IMAGE_TYPES)
        img = Image.new("RGB", (100, 100), color="blue")
        img_io = BytesIO()
        img.save(img_io, format="TIFF")
        img_io.seek(0)

        with pytest.raises(ValidationError) as exc_info:
            compress_image(img_io)
        assert "unsupported" in str(exc_info.value).lower()

    def test_compress_image_exif_orientation_preserved(self):
        """EXIF orientation metadata is correctly applied."""
        # Create an image with EXIF orientation
        img = Image.new("RGB", (200, 100), color="green")

        # Add EXIF data for rotation (orientation tag 6 = rotate 90 CW)
        exif = img.getexif()
        exif[0x0112] = 6  # Orientation tag
        img_io = BytesIO()
        img.save(img_io, format="JPEG", exif=exif)
        img_io.seek(0)

        # Compress the image
        compressed = compress_image(img_io)

        # Open the compressed image
        compressed.seek(0)
        result_img = Image.open(compressed)

        # The image should have been rotated (width and height swapped)
        # Original was 200x100, after 90° rotation should be 100x200
        assert result_img.width == 100
        assert result_img.height == 200

    def test_compress_image_rgba_conversion(self):
        """RGBA images are correctly converted to RGB."""
        # Create an RGBA image
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)

        # Compress the image
        compressed = compress_image(img_io)

        # Open the compressed image
        compressed.seek(0)
        result_img = Image.open(compressed)

        # Should be converted to RGB
        assert result_img.mode == "RGB"
        # Should be saved as JPEG
        assert result_img.format == "JPEG"

    def test_compress_image_supported_formats(self):
        """Normal JPEG and PNG images are processed successfully."""
        # Test JPEG
        jpeg_img = Image.new("RGB", (1000, 1000), color="red")
        jpeg_io = BytesIO()
        jpeg_img.save(jpeg_io, format="JPEG")
        jpeg_io.seek(0)

        compressed_jpeg = compress_image(jpeg_io)
        compressed_jpeg.seek(0)
        result_jpeg = Image.open(compressed_jpeg)
        assert result_jpeg.width <= 800
        assert result_jpeg.height <= 800

        # Test PNG (should be converted to JPEG)
        png_img = Image.new("RGB", (1000, 1000), color="blue")
        png_io = BytesIO()
        png_img.save(png_io, format="PNG")
        png_io.seek(0)

        compressed_png = compress_image(png_io)
        compressed_png.seek(0)
        result_png = Image.open(compressed_png)
        assert result_png.format == "JPEG"
        assert result_png.width <= 800
        assert result_png.height <= 800


class TestSavedViewModel:
    """Tests for the SavedView model."""

    def test_saved_view_str_representation(self, user, db):
        """The string representation includes username and view name."""

        saved_view = SavedView.objects.create(
            user=user,
            name="My Favorite Books",
        )

        assert str(saved_view) == f"{user.username} - My Favorite Books"

    def test_saved_view_unique_together_constraint(self, user, db):
        """User cannot have multiple views with the same name."""
        from django.db import IntegrityError

        # Create first view
        SavedView.objects.create(user=user, name="My View")

        # Attempting to create another view with the same name should fail
        with pytest.raises(IntegrityError):
            SavedView.objects.create(user=user, name="My View")

    def test_saved_view_default_values(self, user, db):
        """SavedView has correct default values for filters and preferences."""

        saved_view = SavedView.objects.create(user=user, name="Default View")

        assert saved_view.filter_types == []
        assert saved_view.filter_statuses == []
        assert saved_view.filter_scores == []
        assert saved_view.filter_contributor_id is None
        assert saved_view.filter_review_from == ""
        assert saved_view.filter_review_to == ""
        assert saved_view.filter_has_review == ""
        assert saved_view.filter_has_cover == ""
        assert saved_view.sort == "-review_date"
        assert saved_view.view_mode == "grid"

    def test_saved_view_stores_filter_parameters(self, user, db):
        """SavedView correctly stores all filter parameters."""

        saved_view = SavedView.objects.create(
            user=user,
            name="Filtered View",
            filter_types=["BOOK", "FILM"],
            filter_statuses=["COMPLETED"],
            filter_scores=["8", "9", "10"],
            filter_contributor_id=1,
            filter_review_from="2024-01-01",
            filter_review_to="2024-12-31",
            filter_has_review="yes",
            filter_has_cover="no",
            sort="-score",
            view_mode="list",
        )

        saved_view.refresh_from_db()

        assert saved_view.filter_types == ["BOOK", "FILM"]
        assert saved_view.filter_statuses == ["COMPLETED"]
        assert saved_view.filter_scores == ["8", "9", "10"]
        assert saved_view.filter_contributor_id == 1
        assert saved_view.filter_review_from == "2024-01-01"
        assert saved_view.filter_review_to == "2024-12-31"
        assert saved_view.filter_has_review == "yes"
        assert saved_view.filter_has_cover == "no"
        assert saved_view.sort == "-score"
        assert saved_view.view_mode == "list"

    def test_saved_view_updated_at_auto_updates(self, user, db):
        """The updated_at field is automatically updated on save."""
        # Freeze time at a specific moment
        with freeze_time("2024-01-01 12:00:00") as frozen_time:
            # Create saved view at this frozen time
            saved_view = SavedView.objects.create(user=user, name="Test View")
            saved_view.refresh_from_db()
            original_updated_at = saved_view.updated_at

            # Move time forward by 1 hour
            frozen_time.move_to("2024-01-01 13:00:00")

            # Update and save again
            saved_view.name = "Updated View Name"
            saved_view.save()

            # Refresh from database
            saved_view.refresh_from_db()

            # updated_at should be more recent than original
            assert saved_view.updated_at > original_updated_at

    def test_get_filter_url_with_defaults(self, user, db):
        """get_filter_url returns URL with default sort and view_mode."""
        saved_view = SavedView.objects.create(user=user, name="Default View")

        url = saved_view.get_filter_url()

        assert url == "/?sort=-review_date&view_mode=grid"

    def test_get_filter_url_with_list_filters(self, user, db):
        """get_filter_url includes list filters (type, status, score) as repeated params."""
        saved_view = SavedView.objects.create(
            user=user,
            name="Filtered View",
            filter_types=["BOOK", "FILM"],
            filter_statuses=["COMPLETED"],
            filter_scores=["9", "10"],
        )

        url = saved_view.get_filter_url()

        # Check that list params are repeated
        assert "type=BOOK" in url
        assert "type=FILM" in url
        assert "status=COMPLETED" in url
        assert "score=9" in url
        assert "score=10" in url

    def test_get_filter_url_with_optional_filters(self, user, db):
        """get_filter_url includes optional filters only when they have values."""
        saved_view = SavedView.objects.create(
            user=user,
            name="Full Filters",
            filter_contributor_id=42,
            filter_review_from="2024-01",
            filter_review_to="2024-12",
            filter_has_review="yes",
            filter_has_cover="no",
        )

        url = saved_view.get_filter_url()

        assert "contributor=42" in url
        assert "review_from=2024-01" in url
        assert "review_to=2024-12" in url
        assert "has_review=yes" in url
        assert "has_cover=no" in url

    def test_get_filter_url_excludes_empty_optional_filters(self, user, db):
        """get_filter_url excludes optional filters when empty."""
        saved_view = SavedView.objects.create(
            user=user,
            name="Minimal View",
            filter_contributor_id=None,  # Empty
            filter_review_from="",  # Empty
        )

        url = saved_view.get_filter_url()

        assert "contributor" not in url
        assert "review_from" not in url
