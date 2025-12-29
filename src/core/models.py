from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD
from partial_date import PartialDateField
from PIL import Image, ImageOps

# Security limits for image processing
MAX_IMAGE_PIXELS = 89_478_485  # ~8000x11000 pixels, default PIL limit
MAX_FILE_SIZE_MB = 10  # Maximum file size in megabytes
ALLOWED_IMAGE_TYPES = {"JPEG", "PNG", "GIF", "BMP", "WEBP"}


def compress_image(image, max_size=(800, 800), quality=85):
    """
    Compress and resize an image to optimize storage with security validations.

    Args:
        image: The image file to compress
        max_size: Maximum dimensions (width, height) - default 800x800
        quality: JPEG quality (1-100) - default 85

    Returns:
        ContentFile with compressed image data

    Raises:
        ValidationError: If the image is invalid, too large, or in an unsupported format
    """
    output = None
    img = None

    try:
        # Step 1: Validate file size (in bytes)
        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        if hasattr(image, "size") and image.size > max_size_bytes:
            raise ValidationError(_("Image file size exceeds %sMB limit.") % MAX_FILE_SIZE_MB)

        # Step 2: Set decompression bomb protection
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        # Step 3: Open and verify the image
        img = Image.open(image)
        img.verify()  # Verify it's a valid image file

        # Re-open after verify (verify closes the file)
        image.seek(0)
        img = Image.open(image)

        # Step 4: Validate image format
        if img.format not in ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                _("Unsupported image format: %s. Allowed: %s") % (img.format, ", ".join(ALLOWED_IMAGE_TYPES))
            )

        # Step 5: Preserve EXIF orientation
        img = ImageOps.exif_transpose(img)

        # Step 6: Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background

        # Step 7: Resize while preserving aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Step 8: Save to buffer
        output = BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)

        return ContentFile(output.read())

    except Image.DecompressionBombError as e:
        raise ValidationError(_("Image is too large (possible decompression bomb attack).")) from e
    except (OSError, Image.UnidentifiedImageError) as e:
        raise ValidationError(_("Invalid or corrupted image file.")) from e
    finally:
        # Clean up resources
        if img:
            img.close()
        if output:
            output.close()


class Agent(models.Model):
    """Model for an agent entity that can be contributor for a media."""

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    name = models.CharField(
        verbose_name=_("Name"),
        blank=False,
        max_length=255,
    )

    def __str__(self):
        return self.name


class Media(models.Model):
    """Model for a piece of media or work of art (book, game, tv series, film, etc.)"""

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    title = models.CharField(
        verbose_name=_("Title"),
        null=False,
        blank=False,
        max_length=255,
    )
    contributors = models.ManyToManyField(
        Agent,
        verbose_name=_("Contributor"),
        blank=True,
        related_name="media",
    )
    media_type = models.CharField(
        verbose_name=_("Media type"),
        null=False,
        blank=False,
        choices={
            "BOOK": _("Book"),
            "GAME": _("Video game"),
            "MUSIC": _("Music"),
            "COMIC": _("Comic"),
            "FILM": _("Film"),
            "TV": _("TV series"),
            "PERF": _("Show/performance"),
            "BROADCAST": _("Broadcast (podcast, web series, etc.)"),
        },
    )
    status = models.CharField(
        verbose_name=_("Status"),
        null=False,
        blank=False,
        choices={
            "PLANNED": _("Planned"),
            "IN_PROGRESS": _("In progress"),
            "COMPLETED": _("Completed"),
            "PAUSED": _("Paused"),
            "DNF": _("Did not finish"),
        },
        default="PLANNED",
    )
    pub_year = models.IntegerField(
        verbose_name=_("Release year"),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-4000, _("Year must be between -4000 and 2100.")),
            MaxValueValidator(2200, _("Year must be between -4000 and 2100.")),
        ],
    )
    review = MarkdownField(
        verbose_name=_("Review"),
        null=False,
        blank=True,
        rendered_field="review_rendered",
        validator=VALIDATOR_STANDARD,
    )
    review_rendered = RenderedMarkdownField(
        null=False,
        blank=True,
    )
    score = models.IntegerField(
        verbose_name=_("Review score"),
        null=True,
        blank=True,
        choices={
            1: _("Detested"),
            2: _("Hated"),
            3: _("Disliked"),
            4: _("Not appreciated"),
            5: _("Moderately appreciated"),
            6: _("Appreciated"),
            7: _("Enjoyed"),
            8: _("Really enjoyed"),
            9: _("Loved"),
            10: _("Adored"),
        },
    )
    review_date = PartialDateField(
        verbose_name=_("Review date"),
        null=True,
        blank=True,
    )
    cover = models.ImageField(
        verbose_name=_("Cover image"),
        upload_to="covers/",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Override save to compress cover image before saving.

        This method detects new file uploads by checking for the _file attribute
        set by Django's file handling. This avoids unnecessary compression on
        saves that don't involve new file uploads.
        """
        # Only compress if a new file was uploaded (has _file attribute)
        if self.cover and hasattr(self.cover, "_file") and self.cover._file:  # noqa: SLF001
            compressed = compress_image(self.cover)
            self.cover.save(self.cover.name, compressed, save=False)

        super().save(*args, **kwargs)
