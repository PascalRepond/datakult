"""View of the home page: the media rated this year, then rows of the media to put forward."""

from django.contrib.auth.decorators import login_required
from django.http import QueryDict
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from core import stats as media_stats
from core.models import Media, Status
from core.queries import LIST_URL_SESSION_KEY, filter_media

ROW_SIZE = 12


def _row(title, query="", ordering=None, **filters):
    """
    Return a row: its title, the URL of the list it starts, and its first media.

    The media are those the list shows for `query`, in its order (latest reviewed first by default),
    narrowed down by `filters` and ordered by `ordering` when given.
    """
    media = filter_media(QueryDict(query))[0].filter(**filters)
    if ordering:
        media = media.order_by(ordering)
    url = f"{reverse('media_list')}?{query}" if query else reverse("media_list")
    return {"title": title, "url": url, "media": list(media[:ROW_SIZE])}


@login_required
def home(request):
    """Home page: the types of the media rated this year and rows of media, or an invitation to add a first one."""
    # Remember the home page as the page to go back to, as the list does
    request.session[LIST_URL_SESSION_KEY] = request.get_full_path()
    year = timezone.localdate().year
    type_counts = media_stats.count_per_type(media_stats.filter_by_year(media_stats.rated_media(), year))
    type_counts = [row for row in type_counts if row["count"]]
    rows = {
        "in_progress": _row(Status.IN_PROGRESS.label, "status=IN_PROGRESS", "-updated_at"),
        "recently_rated": _row(_("Recently rated"), score__isnull=False),
        "planned": _row(Status.PLANNED.label, "status=PLANNED", "-updated_at"),
        "empty_review": _row(_("Empty review"), "status=COMPLETED&status=DNF&has_review=empty"),
    }
    context = {
        "year": year,
        "type_counts": type_counts,
        "rated_count": sum(row["count"] for row in type_counts),
        **rows,
        "library_is_empty": not any(row["media"] for row in rows.values()) and not Media.objects.exists(),
    }
    return render(request, "base/home.html", context)
