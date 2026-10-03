"""Media queryset and pagination utilities."""

import contextlib

from django.core.paginator import Paginator
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.urls import reverse

from .filters import SORT_OPTIONS, apply_filters, extract_filters, get_field_choices, resolve_sorting
from .models import Media

# Session key of the URL of the media list as last shown, filters included
LIST_URL_SESSION_KEY = "list_url"


def get_list_url(request):
    """Return the URL of the media list as last shown, to lead back to it with its filters."""
    return request.session.get(LIST_URL_SESSION_KEY, reverse("home"))


def build_search_queryset(query):
    """Build a filtered queryset based on search query."""
    q_objects = (
        Q(title__icontains=query)
        | Q(contributors__name__icontains=query)
        | Q(review__icontains=query)
        | Q(tags__name__icontains=query)
    )

    # Try to parse query as a year (integer)
    with contextlib.suppress(ValueError):
        parsed_year = int(query)
        q_objects |= Q(pub_year__exact=parsed_year)
    return Media.objects.filter(q_objects).prefetch_related("tags", "contributors").distinct()


def build_media_context(request):
    """
    Build and filter media queryset from request parameters.

    Returns a context_dict ready for rendering.
    This consolidates the common logic used by index and load_more_media views.
    """
    sort = resolve_sorting(request)
    filters = extract_filters(request)
    search_query = request.GET.get("search", "").strip()

    # Build queryset based on whether it's a search or not
    queryset = (
        build_search_queryset(search_query)
        if search_query
        else Media.objects.all().prefetch_related("tags", "contributors")
    )

    # Apply filters and sorting
    queryset, contributor, tag = apply_filters(queryset, filters)
    # Titles sort ignoring case, media without the sorted value come last, and media that tie come last updated first
    name = sort.lstrip("-")
    field = Lower(name) if name == "title" else F(name)
    order = field.desc(nulls_last=True) if sort.startswith("-") else field.asc(nulls_last=True)
    queryset = queryset.order_by(order, "-updated_at")

    # Pagination: 20 items per page
    page_number = request.GET.get("page", 1)
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page_number)

    # One per filter badge
    active_filter_count = (
        len(filters["type"])
        + len(filters["status"])
        + len(filters["score"])
        + bool(filters["release_from"] or filters["release_to"])
        + bool(filters["review_from"] or filters["review_to"])
        + bool(filters["has_review"])
        + bool(filters["has_cover"])
        + bool(contributor)
        + bool(tag)
    )

    return {
        "media_list": page_obj.object_list,
        "page_obj": page_obj,
        # Tells an empty library apart from filters that match nothing
        "library_is_empty": not paginator.count and not Media.objects.exists(),
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "active_filter_count": active_filter_count,
        "contributor": contributor,
        "tag": tag,
        "filters": filters,
        **get_field_choices(),
    }
