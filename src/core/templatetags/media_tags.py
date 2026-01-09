"""Custom template tags for media-related functionality."""

from django import template

register = template.Library()


MEDIA_TYPE_ICONS = {
    "BOOK": "book-open",
    "GAME": "gamepad",
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

STATUS_CLASSES = {
    "PLANNED": "badge-accent",
    "IN_PROGRESS": "badge-info",
    "COMPLETED": "badge-success",
    "PAUSED": "badge-warning",
    "DNF": "badge-error",
}

FILTER_PARAMS = {
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

    icon_name = MEDIA_TYPE_ICONS.get(media_type, "circle-question-mark")
    size_class = SIZE_CLASSES.get(size, "h-4")

    return {
        "icon_name": icon_name,
        "size_class": size_class,
    }


@register.filter
def status_badge_class(status):
    """
    Return the appropriate DaisyUI badge class for a given status.

    Args:
        status: The media status (PLANNED, IN_PROGRESS, etc.)

    Returns:
        String with DaisyUI badge class name

    Example usage:
        <span class="badge {{ media.status|status_badge_class }}">
    """

    return STATUS_CLASSES.get(status, "badge-ghost")


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
        <a href="?{% query_string request view_mode='grid' %}">Grid</a>
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


@register.filter
def toggle_sort_direction(sort_value):
    """
    Toggle the direction of a sort parameter.

    Args:
        sort_value: Current sort value (e.g., '-review_date' or 'review_date')

    Returns:
        Sort value with inverted direction

    Example usage:
        {{ sort|toggle_sort_direction }}
    """
    if not sort_value:
        return "review_date"

    if sort_value.startswith("-"):
        return sort_value[1:]
    return f"-{sort_value}"


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
