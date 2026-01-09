"""Media queryset and pagination utilities."""

from django.core.paginator import Paginator
from django.db.models import Q

from .filters import apply_filters, extract_filters, get_field_choices, resolve_sorting
from .models import Media, SavedView


def build_search_queryset(query):
    """Build a filtered queryset based on search query."""
    q_objects = Q(title__icontains=query) | Q(contributors__name__icontains=query) | Q(review__icontains=query)

    # Try to parse query as a year (integer)
    try:
        parsed_year = int(query)
        q_objects |= Q(pub_year__exact=parsed_year)
    except ValueError:
        # Not a valid integer, skip year filtering
        pass

    return Media.objects.filter(q_objects).distinct()


def build_media_context(request):
    """
    Build and filter media queryset from request parameters.

    Returns a context_dict ready for rendering.
    This consolidates the common logic used by index and load_more_media views.
    """
    view_mode = request.GET.get("view_mode", "grid")
    sort_field, sort = resolve_sorting(request)
    filters = extract_filters(request)
    search_query = request.GET.get("search", "").strip()

    # Build queryset based on whether it's a search or not
    queryset = build_search_queryset(search_query) if search_query else Media.objects.all()

    # Apply filters and sorting
    queryset, contributor = apply_filters(queryset, filters)
    queryset = queryset.order_by(sort)

    # Pagination: 20 items per page
    page_number = request.GET.get("page", 1)
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page_number)

    # Saved views for the current user
    saved_views = request.user.saved_views.all() if request.user.is_authenticated else SavedView.objects.none()

    return {
        "media_list": page_obj.object_list,
        "page_obj": page_obj,
        "view_mode": view_mode,
        "sort_field": sort_field,
        "sort": sort,
        "contributor": contributor,
        "filters": filters,
        "saved_views": saved_views,
        **get_field_choices(),
    }
