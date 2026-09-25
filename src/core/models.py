from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD
from partial_date import PartialDateField
from PIL import Image, ImageOps

# Security limits for image processing, on top of the decompression bomb limit of PIL
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
    if getattr(image, "size", 0) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValidationError(_("Image file size exceeds %(max_size)sMB limit.") % {"max_size": MAX_FILE_SIZE_MB})

    try:
        # Verify that the file is a valid image, which closes it: it is opened again to be compressed
        with Image.open(image) as img:
            img.verify()
        image.seek(0)
        with Image.open(image) as img:
            if img.format not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(
                    _("Unsupported image format: %(format)s. Allowed: %(allowed)s")
                    % {"format": img.format, "allowed": ", ".join(ALLOWED_IMAGE_TYPES)}
                )
            compressed = ImageOps.exif_transpose(img)

            # Flatten transparent images on a white background, as JPEG has no transparency
            if compressed.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", compressed.size, (255, 255, 255))
                if compressed.mode == "P":
                    compressed = compressed.convert("RGBA")
                background.paste(compressed, mask=compressed.split()[-1] if compressed.mode == "RGBA" else None)
                compressed = background

            compressed.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            compressed.save(output, format="JPEG", quality=quality, optimize=True)
    except Image.DecompressionBombError as e:
        raise ValidationError(_("Image is too large (possible decompression bomb attack).")) from e
    except (OSError, Image.UnidentifiedImageError) as e:
        raise ValidationError(_("Invalid or corrupted image file.")) from e

    return ContentFile(output.getvalue())


def dominant_color(image):
    """Return the most common colour of an image as a hex string, or an empty string if it cannot be read."""
    try:
        with Image.open(image) as img:
            img.thumbnail((64, 64))
            palette = img.convert("RGB").quantize(colors=8)
    except OSError, Image.DecompressionBombError:
        return ""
    _count, index = max(palette.getcolors())
    red, green, blue = palette.getpalette()[index * 3 : index * 3 + 3]
    return f"#{red:02x}{green:02x}{blue:02x}"


class MediaType(models.TextChoices):
    BOOK = "BOOK", _("Book")
    GAME = "GAME", _("Video game")
    MUSIC = "MUSIC", _("Music")
    COMIC = "COMIC", _("Comic")
    FILM = "FILM", _("Film")
    TV = "TV", _("TV series")
    PERF = "PERF", _("Show/performance")
    BROADCAST = "BROADCAST", _("Broadcast")


class Status(models.TextChoices):
    PLANNED = "PLANNED", _("Planned")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    COMPLETED = "COMPLETED", _("Completed")
    PAUSED = "PAUSED", _("Paused")
    DNF = "DNF", _("Did not finish")


class Score(models.IntegerChoices):
    """Review scores, from 1 to 10, named by the verdict they stand for."""

    DETESTED = 1, _("Detested")
    HATED = 2, _("Hated")
    DISLIKED = 3, _("Disliked")
    NOT_APPRECIATED = 4, _("Not appreciated")
    MODERATELY_APPRECIATED = 5, _("Moderately appreciated")
    APPRECIATED = 6, _("Appreciated")
    ENJOYED = 7, _("Enjoyed")
    REALLY_ENJOYED = 8, _("Really enjoyed")
    LOVED = 9, _("Loved")
    ADORED = 10, _("Adored")


class TimestampedModel(models.Model):
    """Base model keeping when an object was created and last updated."""

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class NamedModel(TimestampedModel):
    """Base model of the entities known by a unique name, such as contributors and tags."""

    name = models.CharField(
        verbose_name=_("Name"),
        blank=False,
        max_length=100,
        unique=True,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Agent(NamedModel):
    """Model for an agent entity that can be contributor for a media."""

    class Meta:
        verbose_name = _("Agent")
        verbose_name_plural = _("Agents")


class Tag(NamedModel):
    """Model for tags/genres that can be applied to media."""

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")


class Media(TimestampedModel):
    """Model for a piece of media or work of art (book, game, tv series, film, etc.)"""

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
    tags = models.ManyToManyField(
        Tag,
        verbose_name=_("Tags"),
        blank=True,
        related_name="media",
    )
    media_type = models.CharField(
        verbose_name=_("Media type"),
        null=False,
        blank=False,
        choices=MediaType,
    )
    external_uri = models.URLField(
        verbose_name=_("External URI"),
        max_length=500,
        null=False,
        blank=True,
        default="",
        help_text=_("Link to an external page about this media (e.g., official site, IMDb, Goodreads, etc.)"),
    )
    status = models.CharField(
        verbose_name=_("Status"),
        null=False,
        blank=False,
        choices=Status,
        default=Status.PLANNED,
    )
    pub_year = models.IntegerField(
        verbose_name=_("Release year"),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-4000, _("Year must be between -4000 and 2200.")),
            MaxValueValidator(2200, _("Year must be between -4000 and 2200.")),
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
        choices=Score,
    )
    review_date = PartialDateField(
        verbose_name=_("Review date"),
        null=True,
        blank=True,
        help_text=_("Either a full date or just year and month, or only year."),
    )
    cover = models.ImageField(
        verbose_name=_("Cover image"),
        upload_to="covers/",
        blank=True,
        null=True,
    )
    # Fills the space left around a cover whose shape differs from its frame
    cover_color = models.CharField(max_length=7, blank=True, default="", editable=False)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Override save to compress cover image before saving, and keep the colour of the cover.

        This method detects new file uploads by checking for the _file attribute
        set by Django's file handling. This avoids unnecessary compression on
        saves that don't involve new file uploads.
        """
        # Only compress if a new file was uploaded (has _file attribute)
        if self.cover and hasattr(self.cover, "_file") and self.cover._file:  # noqa: SLF001
            compressed = compress_image(self.cover)
            self.cover_color = dominant_color(compressed)
            self.cover.save(Path(self.cover.name).with_suffix(".jpg").name, compressed, save=False)
        elif not self.cover:
            self.cover_color = ""

        super().save(*args, **kwargs)


class SavedView(TimestampedModel):
    """Model for saving filtered views with custom names."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    name = models.CharField(max_length=100)

    # Filter parameters
    filter_types = models.JSONField(default=list, blank=True)
    filter_statuses = models.JSONField(default=list, blank=True)
    filter_scores = models.JSONField(default=list, blank=True)
    filter_contributor_id = models.IntegerField(null=True, blank=True)
    filter_tag_id = models.IntegerField(null=True, blank=True)
    filter_review_from = models.CharField(max_length=20, blank=True, default="")
    filter_review_to = models.CharField(max_length=20, blank=True, default="")
    filter_has_review = models.CharField(max_length=10, blank=True, default="")
    filter_has_cover = models.CharField(max_length=10, blank=True, default="")

    # View preferences
    sort = models.CharField(max_length=50, default="-review_date")

    class Meta:
        unique_together = [["user", "name"]]
        ordering = ["name"]
        verbose_name = _("Saved view")
        verbose_name_plural = _("Saved views")

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    def get_filter_url(self):
        """Build the URL with all filters applied."""
        params = [
            *[("type", val) for val in self.filter_types],
            *[("status", val) for val in self.filter_statuses],
            *[("score", val) for val in self.filter_scores],
        ]
        optional_filters = [
            ("contributor", self.filter_contributor_id),
            ("tag", self.filter_tag_id),
            ("review_from", self.filter_review_from),
            ("review_to", self.filter_review_to),
            ("has_review", self.filter_has_review),
            ("has_cover", self.filter_has_cover),
        ]
        params.extend((key, value) for key, value in optional_filters if value)
        params.append(("sort", self.sort))
        return f"{reverse('home')}?{urlencode(params)}"
