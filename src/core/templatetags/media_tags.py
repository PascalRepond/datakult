"""Custom template tags for media-related functionality."""

from urllib.parse import parse_qsl, urlsplit

from django import template
from django.utils import formats

register = template.Library()


MEDIA_TYPE_ICONS = {
    "BOOK": "book-open",
    "GAME": "gamepad-2",
    "MUSIC": "disc-3",
    "COMIC": "book-image",
    "FILM": "film",
    "TV": "tv",
    "PERF": "ticket",
    "BROADCAST": "podcast",
}

SIZE_CLASSES = {
    "sm": "h-4",
    "md": "h-5",
    "lg": "h-8",
}

STATUS_ICONS = {
    "PLANNED": "clock",
    "IN_PROGRESS": "play",
    "PAUSED": "pause",
    "COMPLETED": "circle-check",
    "DNF": "circle-x",
}

# Upper score bound of each verdict colour: disliked, mixed, appreciated, enjoyed, loved
SCORE_COLORS = (
    (4, "text-red-500"),
    (5, "text-amber-500"),
    (6, "text-lime-500"),
    (8, "text-green-500"),
    (10, "text-emerald-600"),
)

FILTER_PARAMS = {
    "tag",
    "contributor",
    "type",
    "status",
    "score",
    "review_from",
    "review_to",
    "has_review",
    "has_cover",
}


@register.inclusion_tag("partials/media_items/media_icon.html")
def media_icon(media_type, size="sm"):
    """
    Render a lucide icon based on media type.

    Args:
        media_type: The type of media (BOOK, GAME, MUSIC, etc.)
        size: Icon size (sm, md, lg) - default 'sm'

    Returns:
        Context dict with icon_name and size_class

    Example usage:
        {% load media_tags %}
        {% media_icon media.media_type size="md" %}
    """

    size_class = SIZE_CLASSES.get(size, "h-4")

    return {
        "icon_name": type_icon(media_type),
        "size_class": size_class,
    }


@register.filter
def type_icon(media_type):
    """
    Return the lucide icon of a media type.

    Example usage:
        {% lucide media.media_type|type_icon %}
    """
    return MEDIA_TYPE_ICONS.get(media_type, "circle-question-mark")


@register.filter
def status_icon(status):
    """
    Return the lucide icon of a status, the same as its entry in the sidebar.

    Example usage:
        {% lucide media.status|status_icon %}
    """
    return STATUS_ICONS.get(status, "circle-question-mark")


@register.filter
def score_color(score):
    """
    Return the text colour class of a score (1-10), from red for disliked media to green for loved ones.

    Example usage:
        <span class="radial-progress {{ media.score|score_color }}">
    """
    return next(color for bound, color in SCORE_COLORS if score <= bound)


@register.filter
def domain(url):
    """
    Return the domain of a URL, without its www prefix, or the value itself when it has none.

    Example usage:
        {{ media.external_uri|domain }}  ->  "themoviedb.org"
    """
    host = urlsplit(url).hostname
    return host.removeprefix("www.") if host else url


@register.filter
def partial_date(value):
    """
    Format a partial date in the active language, down to its own precision.

    Example usage:
        {{ media.review_date|partial_date }}  ->  "12 mai 2024", "mai 2024" or "2024"
    """
    if not value:
        return ""
    if value.precisionYear():
        return str(value.date.year)
    date_format = "YEAR_MONTH_FORMAT" if value.precisionMonth() else "DATE_FORMAT"
    return formats.date_format(value.date, date_format)


@register.simple_tag
def query_string(request, **kwargs):
    """
    Build a query string from current GET parameters, with updates from kwargs.

    Args:
        request: The current request object
        **kwargs: Parameters to add/update/remove (None to remove)

    Returns:
        Query string with all parameters (including multi-value params)

    Example usage:
        <a href="?{% query_string request sort='-score' %}">Best first</a>
        <a href="?{% query_string request sort=None %}">Clear sort</a>
    """
    if not hasattr(request, "GET"):
        return ""

    # Start with a copy of current GET parameters (handles multi-value)
    params = request.GET.copy()

    # Update with provided kwargs
    for key, value in kwargs.items():
        if value is None:
            # Remove parameter
            params.pop(key, None)
        else:
            # Set parameter (replaces all values)
            params[key] = value

    # Build query string
    return params.urlencode() if params else ""


@register.simple_tag
def query_string_exclude(request, *exclude_keys):
    """
    Build a query string from current GET parameters, excluding specified keys.

    Args:
        request: The current request object
        *exclude_keys: Parameter names to exclude

    Returns:
        Query string with all parameters except excluded ones

    Example usage:
        <a href="?{% query_string_exclude request 'page' %}">Without page</a>
    """
    if not hasattr(request, "GET"):
        return ""

    params = request.GET.copy()

    for key in exclude_keys:
        params.pop(key, None)

    return params.urlencode() if params else ""


@register.simple_tag
def has_filters(request):
    """
    Check if any filter parameters are present in the request.

    Args:
        request: The current request object

    Returns:
        True if any filter parameters exist, False otherwise

    Example usage:
        {% if has_filters request %}...{% endif %}
    """
    if not hasattr(request, "GET"):
        return False
    return any((param in request.GET) and any(v != "" for v in request.GET.getlist(param)) for param in FILTER_PARAMS)


def _url_state(path, query):
    """Return the path and the sorted non-empty query parameters of a URL, without the page."""
    params = sorted((key, value) for key, value in parse_qsl(query) if value and key != "page")
    return path, params


@register.simple_tag
def is_current_url(request, url):
    """
    Check if a URL points to the current page, whatever the order of its parameters.

    Example usage:
        {% is_current_url request view.get_filter_url as is_active %}
    """
    target = urlsplit(url)
    return _url_state(request.path, request.META.get("QUERY_STRING", "")) == _url_state(target.path, target.query)


@register.simple_tag
def status_filter_matches(request, *expected_statuses):
    """
    Check if the status filter exactly matches the expected statuses.

    Args:
        request: The current request object
        *expected_statuses: One or more status values to check for

    Returns:
        True if status filter exactly matches expected values, False otherwise

    Example usage:
        {% status_filter_matches request 'COMPLETED' 'DNF' as is_active %}
        {% if is_active %}...{% endif %}
    """
    if not hasattr(request, "GET"):
        return False
    current_statuses = set(request.GET.getlist("status"))
    expected_set = set(expected_statuses)
    return current_statuses == expected_set
