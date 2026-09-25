"""Views saving the filters of the media list as named views, and deleting them."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from core.filters import DEFAULT_SORT, filter_errors
from core.models import SavedView


@login_required
def saved_view_save(request):
    """Save the filters of the list as a view, replacing the view of the same name if there is one."""
    if request.method != "POST":
        return redirect("home")

    view_name = request.POST.get("view_name", "").strip()
    if not view_name:
        messages.error(request, _("View name is required"))
        return redirect("home")
    if errors := filter_errors(request.POST):
        for error in errors:
            messages.error(request, error)
        return redirect("home")

    saved_view, created = SavedView.objects.update_or_create(
        user=request.user,
        name=view_name,
        defaults={
            "filter_types": request.POST.getlist("type"),
            "filter_statuses": request.POST.getlist("status"),
            "filter_scores": request.POST.getlist("score"),
            "filter_contributor_id": request.POST.get("contributor") or None,
            "filter_tag_id": request.POST.get("tag") or None,
            "filter_review_from": request.POST.get("review_from", ""),
            "filter_review_to": request.POST.get("review_to", ""),
            "filter_has_review": request.POST.get("has_review", ""),
            "filter_has_cover": request.POST.get("has_cover", ""),
            "sort": request.POST.get("sort", DEFAULT_SORT),
        },
    )
    message = _("View '%(name)s' saved successfully") if created else _("View '%(name)s' has been updated")
    messages.success(request, message % {"name": view_name})

    # Show the list with the filters of the view
    return redirect(saved_view.get_filter_url())


@login_required
def saved_view_delete(request, pk):
    """Delete a saved view."""
    if request.method != "POST":
        return redirect("home")

    try:
        saved_view = SavedView.objects.get(pk=pk, user=request.user)
    except SavedView.DoesNotExist:
        messages.error(request, _("View not found"))
    else:
        saved_view.delete()
        messages.success(request, _("View '%(name)s' deleted successfully") % {"name": saved_view.name})

    # Redirect to home to refresh the sidebar
    return redirect("home")
