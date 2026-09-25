"""Media filtering and sorting utilities."""

import contextlib

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from partial_date import PartialDate

from .models import Agent, Media, Tag

# Sort values, with a descending sign, and how they order the list
SORT_OPTIONS = [
    ("-review_date", gettext_lazy("Recently rated")),
    ("review_date", gettext_lazy("Oldest rated")),
    ("-score", gettext_lazy("Best scores")),
    ("score", gettext_lazy("Lowest scores")),
]


DEFAULT_SORT = "-review_date"


def resolve_sorting(request):
    """Return the sort of the request when it is one of the sort options, else the default sort."""
    sort = request.GET.get("sort") or request.GET.get("order_by")
    return sort if sort in dict(SORT_OPTIONS) else DEFAULT_SORT


def extract_filters(request):
    """Extract filter parameters from request and return filters dict."""
    filters = {
        "contributor": request.GET.get("contributor", ""),
        "tag": request.GET.get("tag", ""),
        "type": request.GET.getlist("type"),
        "status": request.GET.getlist("status"),
        "score": request.GET.getlist("score"),
        "review_from": request.GET.get("review_from", ""),
        "review_to": request.GET.get("review_to", ""),
        "has_review": request.GET.get("has_review", ""),
        "has_cover": request.GET.get("has_cover", ""),
    }
    filters["has_any"] = any(
        [
            filters["type"],
            filters["status"],
            filters["score"],
            filters["review_from"],
            filters["review_to"],
            filters["has_review"],
            filters["has_cover"],
        ]
    )

    # Add display names for active filters (as list of tuples: (value, label))
    if filters["type"]:
        type_choices_dict = dict(Media.media_type.field.choices)
        filters["type_display"] = [(t, type_choices_dict.get(t, t)) for t in filters["type"]]
    if filters["status"]:
        status_choices_dict = dict(Media.status.field.choices)
        filters["status_display"] = [(s, status_choices_dict.get(s, s)) for s in filters["status"]]
    if filters["score"]:
        score_choices_dict = dict(Media.score.field.choices)
        filters["score_display"] = []
        for s in filters["score"]:
            if s == "none":
                filters["score_display"].append(("none", _("Not rated")))
            else:
                try:
                    filters["score_display"].append((s, score_choices_dict.get(int(s), s)))
                except ValueError:
                    # Skip malformed score values from URL
                    continue

    return filters


def get_field_choices():
    """Return choices for filter fields from the Media model."""
    return {
        "media_type_choices": Media.media_type.field.choices,
        "status_choices": Media.status.field.choices,
        "score_choices": Media.score.field.choices,
    }


def _apply_related_filter(queryset, model, pk_value, filter_field):
    """Apply a filter based on a related model lookup."""
    instance = None
    if pk_value:
        with contextlib.suppress(ValueError, TypeError):
            instance = model.objects.filter(pk=pk_value).first()
        if instance:
            queryset = queryset.filter(**{filter_field: instance})
    return queryset, instance


def apply_contributor_filter(queryset, contributor_id):
    """Apply contributor filter to queryset and return (queryset, contributor)."""
    return _apply_related_filter(queryset, Agent, contributor_id, "contributors")


def apply_tag_filter(queryset, tag_id):
    """Apply tag filter to queryset and return (queryset, tag)."""
    return _apply_related_filter(queryset, Tag, tag_id, "tags")


def apply_type_filter(queryset, media_types):
    """Apply OR filter for media types."""
    return queryset.filter(media_type__in=media_types) if media_types else queryset


def apply_status_filter(queryset, statuses):
    """Apply OR filter for statuses."""
    return queryset.filter(status__in=statuses) if statuses else queryset


def apply_score_filter(queryset, scores):
    """Apply OR filter for scores (including 'none' for null scores)."""
    if not scores:
        return queryset
    score_q = Q()
    for score in scores:
        if score == "none":
            score_q |= Q(score__isnull=True)
        else:
            try:
                score_q |= Q(score=int(score))
            except ValueError:
                # Skip malformed score values from URL
                continue
    return queryset.filter(score_q)


def _review_from_bound(value):
    """
    Return the start date `value` with the coarsest precision it allows.

    Review dates store their precision in the seconds (year < month < day), so a day precision
    bound would exclude year or month precision dates falling on that same day.
    """
    date = PartialDate(value).date
    if date.day != 1:
        return PartialDate(date, PartialDate.DAY)
    if date.month != 1:
        return PartialDate(date, PartialDate.MONTH)
    return PartialDate(date, PartialDate.YEAR)


def apply_date_and_content_filters(queryset, filters):
    """Apply review date, review content, and cover filters."""
    if filters["review_from"]:
        # Skip malformed date values from URL
        with contextlib.suppress(ValueError, TypeError, ValidationError):
            queryset = queryset.filter(review_date__gte=_review_from_bound(filters["review_from"]))
    if filters["review_to"]:
        # Skip malformed date values from URL
        with contextlib.suppress(ValueError, TypeError, ValidationError):
            queryset = queryset.filter(review_date__lte=filters["review_to"])
    if filters["has_review"] == "empty":
        queryset = queryset.filter(Q(review__isnull=True) | Q(review=""))
    elif filters["has_review"] == "filled":
        queryset = queryset.exclude(Q(review__isnull=True) | Q(review=""))
    if filters["has_cover"] == "empty":
        queryset = queryset.filter(Q(cover__isnull=True) | Q(cover=""))
    elif filters["has_cover"] == "filled":
        queryset = queryset.exclude(Q(cover__isnull=True) | Q(cover=""))
    return queryset


def apply_filters(queryset, filters):
    """Apply filters to a queryset and return (queryset, contributor, tag)."""
    queryset, contributor = apply_contributor_filter(queryset, filters["contributor"])
    queryset, tag = apply_tag_filter(queryset, filters["tag"])
    queryset = apply_type_filter(queryset, filters["type"])
    queryset = apply_status_filter(queryset, filters["status"])
    queryset = apply_score_filter(queryset, filters["score"])
    queryset = apply_date_and_content_filters(queryset, filters)
    return queryset, contributor, tag
