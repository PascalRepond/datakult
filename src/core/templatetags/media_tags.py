"""Custom template tags for media-related functionality."""

from django import template

register = template.Library()


MEDIA_TYPE_ICONS = {
    "BOOK": "book-open",
    "GAME": "puzzle-piece",
    "MUSIC": "musical-note",
    "COMIC": "book-open",
    "FILM": "film",
    "TV": "tv",
    "PERF": "ticket",
    "BROADCAST": "microphone",
}

SIZE_CLASSES = {
    "sm": "w-4 h-4",
    "md": "w-6 h-6",
    "lg": "w-8 h-8",
}

STATUS_CLASSES = {
    "PLANNED": "badge-info",
    "IN_PROGRESS": "badge-accent",
    "COMPLETED": "badge-success",
    "PAUSED": "badge-primary",
    "DNF": "badge-error",
}


@register.inclusion_tag("partials/media_items/media_icon.html")
def media_icon(media_type, size="sm"):
    """
    Render a heroicon based on media type.

    Args:
        media_type: The type of media (BOOK, GAME, MUSIC, etc.)
        size: Icon size (sm, md, lg) - default 'sm'

    Returns:
        Context dict with icon_name and size_class

    Example usage:
        {% load media_tags %}
        {% media_icon media.media_type size="md" %}
    """

    icon_name = MEDIA_TYPE_ICONS.get(media_type, "question-mark-circle")
    size_class = SIZE_CLASSES.get(size, "w-4 h-4")

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
