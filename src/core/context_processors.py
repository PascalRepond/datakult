"""Context processors for the core app."""

from functools import lru_cache

from .models import SavedView
from .utils import get_datakult_version


@lru_cache(maxsize=1)
def _cached_version() -> str:
    return get_datakult_version()


def version(_request):
    """Add the application version to the template context.

    Makes the Datakult version available in all templates as {{ version }}.

    Args:
        _request: The HTTP request object (unused but required by Django).

    Returns:
        A dictionary with the version string.
    """
    return {"version": _cached_version()}


def saved_views(request):
    """Add saved views to the template context for authenticated users.

    Args:
        request: The HTTP request object.

    Returns:
        A dictionary with the user's saved views queryset.
    """
    if request.user.is_authenticated:
        return {"saved_views": request.user.saved_views.all()}
    return {"saved_views": SavedView.objects.none()}
