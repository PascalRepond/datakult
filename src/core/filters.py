"""Media filtering and sorting utilities."""

import contextlib

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _

from .models import Agent, Media


def resolve_sorting(request):
    """Return validated sorting info: selected field and normalized sort string (with sign)."""
    default_field = "review_date"
    sort = request.GET.get("sort") or request.GET.get("order_by") or f"-{default_field}"

    raw_field = sort.lstrip("-")
    valid_fields = {"created_at", "updated_at", "review_date", "score"}
    sort_field = raw_field if raw_field in valid_fields else default_field

    is_desc = sort.startswith("-")
    normalized_sort = f"-{sort_field}" if is_desc else sort_field
    return sort_field, normalized_sort


def extract_filters(request):
    """Extract filter parameters from request and return filters dict."""
    filters = {
        "contributor": request.GET.get("contributor", ""),
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


def apply_contributor_filter(queryset, contributor_id):
    """Apply contributor filter to queryset and return (queryset, contributor)."""

    contributor = None
    if contributor_id:
        contributor = Agent.objects.filter(pk=contributor_id).first()
        if contributor:
            queryset = queryset.filter(contributors=contributor)
    return queryset, contributor


def apply_type_filter(queryset, media_types):
    """Apply OR filter for media types."""
    if not media_types:
        return queryset
    return queryset.filter(media_type__in=media_types)


def apply_status_filter(queryset, statuses):
    """Apply OR filter for statuses."""
    if not statuses:
        return queryset
    return queryset.filter(status__in=statuses)


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


def apply_date_and_content_filters(queryset, filters):
    """Apply review date, review content, and cover filters."""
    if filters["review_from"]:
        # Skip malformed date values from URL
        with contextlib.suppress(ValueError, TypeError, ValidationError):
            queryset = queryset.filter(review_date__gte=filters["review_from"])
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
    """Apply filters to a queryset and return (queryset, contributor)."""
    queryset, contributor = apply_contributor_filter(queryset, filters["contributor"])
    queryset = apply_type_filter(queryset, filters["type"])
    queryset = apply_status_filter(queryset, filters["status"])
    queryset = apply_score_filter(queryset, filters["score"])
    queryset = apply_date_and_content_filters(queryset, filters)
    return queryset, contributor
