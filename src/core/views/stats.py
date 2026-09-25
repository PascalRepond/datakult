"""Views of the statistics page."""

import calendar
from datetime import MAXYEAR, MINYEAR

from django.contrib.auth.decorators import login_required
from django.core.paginator import InvalidPage, Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import urlencode

from core import stats as media_stats
from core.models import MediaType

STATS_COVERS_PER_PAGE = 40
MAX_YEAR_LENGTH = 4


def _stats_filters(request):
    """Read the stats page filters: return the year, the media type and the rated media reviewed that year."""
    value = request.GET.get("year", "")
    year = (
        int(value) if len(value) <= MAX_YEAR_LENGTH and value.isdecimal() and MINYEAR <= int(value) < MAXYEAR else None
    )
    media_type = request.GET.get("type")
    if media_type not in MediaType.values:
        media_type = None
    return year, media_type, media_stats.filter_by_year(media_stats.rated_media(), year)


def _stats_covers_page(media, number=1):
    """Page of media shown as covers on the stats page, best scores first, then latest reviews."""
    queryset = media.prefetch_related("contributors").order_by("-score", "-review_date", "-pk")
    return Paginator(queryset, STATS_COVERS_PER_PAGE).page(number)


def _url_with_filters(url_name, **filters):
    """URL of the `url_name` page with the given query string filters, skipping None values."""
    return f"{reverse(url_name)}?{urlencode({key: value for key, value in filters.items() if value is not None})}"


def _review_bounds(year, month=None):
    """Home review date filters covering a year, or one of its months."""
    if month is None:
        return {"review_from": f"{year:04d}-01-01", "review_to": f"{year:04d}-12-31"}
    last_day = calendar.monthrange(year, month)[1]
    return {"review_from": f"{year:04d}-{month:02d}-01", "review_to": f"{year:04d}-{month:02d}-{last_day:02d}"}


@login_required
def stats(request):
    """Statistics on rated media, optionally restricted to a review year and a media type."""
    year, media_type, media = _stats_filters(request)
    # Type counters ignore the type filter, since they are used to pick it
    type_counts = media_stats.count_per_type(media)
    media = media_stats.filter_by_type(media, media_type)

    # Yearly bars narrow the stats down to their year; the other bars link to the media list they count
    per_year = media_stats.count_per_year(media) if year is None else None
    for row in per_year or []:
        row["url"] = _url_with_filters("stats", year=row["label"], type=media_type)
    per_month = media_stats.count_per_month(media, year) if year is not None else None
    for month, row in enumerate(per_month or [], start=1):
        row["url"] = _url_with_filters("home", type=media_type, **_review_bounds(year, month))
    score_distribution = media_stats.score_distribution(media)
    year_bounds = _review_bounds(year) if year else {}
    for row in score_distribution:
        row["url"] = _url_with_filters("home", type=media_type, score=row["label"], **year_bounds)

    # The year picker keeps the type filter; without a year, the yearly chart already holds its years
    if year is None:
        years = [row["label"] for row in reversed(per_year) if row["count"]]
    else:
        years = media_stats.available_years(media_stats.filter_by_type(media_stats.rated_media(), media_type))
    previous_year, next_year = media_stats.adjacent_years(years, year)
    context = {
        "years": years,
        "year": year,
        "previous_year": previous_year,
        "next_year": next_year,
        "media_type": media_type,
        "media_type_label": dict(MediaType.choices).get(media_type),
        "type_counts": type_counts,
        "overview": media_stats.overview(media),
        "covers": _stats_covers_page(media),
        "per_year": per_year,
        "per_month": per_month,
        "score_distribution": score_distribution,
    }
    return render(request, "base/stats.html", context)


@login_required
def stats_covers_htmx(request):
    """HTMX view: load the next page of covers on the stats page."""
    _year, media_type, media = _stats_filters(request)
    try:
        covers = _stats_covers_page(media_stats.filter_by_type(media, media_type), request.GET.get("page"))
    except InvalidPage:
        # Rated media changed since the page was shown: add nothing rather than repeat covers already shown
        return HttpResponse()
    return render(request, "partials/stats/covers_page.html", {"covers": covers})
