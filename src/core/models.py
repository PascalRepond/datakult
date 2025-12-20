from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from markdownfield.models import MarkdownField
from partial_date import PartialDateField


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
    )
    score = models.IntegerField(
        verbose_name=_("Review score"),
        null=True,
        blank=True,
        choices={
            1: _("1⭐ - Detested"),
            2: _("2⭐ - Hated"),
            3: _("3⭐ - Disliked"),
            4: _("4⭐ - Not appreciated"),
            5: _("5⭐ - Moderately appreciated"),
            6: _("6⭐ - Appreciated"),
            7: _("7⭐ - Enjoyed"),
            8: _("8⭐ - Really enjoyed"),
            9: _("9⭐ - Loved"),
            10: _("10⭐ - Adored"),
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
