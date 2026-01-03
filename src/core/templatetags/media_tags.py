"""Custom template tags for media-related functionality."""

from django import template

register = template.Library()


MEDIA_TYPE_ICONS = {
    "BOOK": "book-open",
    "GAME": "computer-desktop",
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
    "PAUSED": "badge-neutral",
    "DNF": "badge-error",
}


@register.inclusion_tag("partials/media-icon.html")
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
