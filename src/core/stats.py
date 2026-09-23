"""Aggregations for the statistics dashboard. Each function works on the media queryset it is given."""

from collections import Counter

from django.db.models import Avg, Count
from django.utils.dates import MONTHS_3
from django.utils.text import capfirst

from .models import Media


def _with_pct(rows):
    """Add a `pct` key (relative to the largest count) used for bar heights."""
    top = max((row["count"] for row in rows), default=0)
    for row in rows:
        row["pct"] = round(row["count"] * 100 / top) if top else 0
    return rows


def _review_dates(media):
    """Return the review dates (PartialDate) of `media`, skipping undated ones."""
    return media.filter(review_date__isnull=False).values_list("review_date", flat=True)


def rated_media():
    """Media with a score: the population all statistics are computed on."""
    return Media.objects.filter(score__isnull=False)


def filter_by_year(media, year=None):
    """Restrict `media` to those reviewed in `year`, whatever the date precision; None keeps everything."""
    if year is None:
        return media
    return media.filter(review_date__gte=f"{year:04d}", review_date__lt=f"{year + 1:04d}")


def filter_by_type(media, media_type=None):
    """Restrict `media` to `media_type`; None keeps everything."""
    return media.filter(media_type=media_type) if media_type else media


def available_years(media):
    """Return the review years of `media`, newest first."""
    return sorted({date.date.year for date in _review_dates(media)}, reverse=True)


def adjacent_years(years, year):
    """Return the closest years before and after `year` among `years`, None when there is none."""
    if year is None:
        return None, None
    return max((y for y in years if y < year), default=None), min((y for y in years if y > year), default=None)


def count_per_type(media):
    """Count media for every media type, in the order of the model choices."""
    counts = dict(media.values_list("media_type").annotate(count=Count("id")).order_by())
    return [
        {"media_type": media_type, "label": label, "count": counts.get(media_type, 0)}
        for media_type, label in Media.media_type.field.choices
    ]


def count_per_year(media):
    """Count media per review year, zero-filling years without any."""
    if counts := Counter(date.date.year for date in _review_dates(media)):
        return _with_pct([{"label": year, "count": counts[year]} for year in range(min(counts), max(counts) + 1)])
    return []


def count_per_month(media, year):
    """Count media per month of `year`, year-only review dates falling in January as the review date filter does."""
    counts = Counter(date.date.month for date in _review_dates(media) if date.date.year == year)
    return _with_pct([{"label": capfirst(MONTHS_3[month]), "count": counts[month]} for month in range(1, 13)])


def score_distribution(media):
    """Count media per score from 1 to 10."""
    counts = dict(media.values_list("score").annotate(count=Count("id")).order_by())
    labels = dict(Media.score.field.choices)
    return _with_pct(
        [{"label": score, "title": labels[score], "count": counts.get(score, 0)} for score in range(1, 11)]
    )


def overview(media):
    """Global figures: media count and average score."""
    totals = media.aggregate(count=Count("id"), average_score=Avg("score"))
    return {
        "count": totals["count"],
        "average_score": round(totals["average_score"], 1) if totals["average_score"] is not None else None,
    }
