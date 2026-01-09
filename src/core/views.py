import tarfile
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from partial_date import PartialDate

from .forms import MediaForm
from .models import Agent, Media, SavedView
from .queries import build_media_context
from .utils import create_backup, delete_orphan_agents_by_ids


@login_required
def index(request):
    """Main view for displaying media list."""
    context = build_media_context(request)
    return render(request, "base/media_index.html", context)


@login_required
def media_detail(request, pk):
    """Display detailed view of a single media item."""
    media = get_object_or_404(Media, pk=pk)
    context = {"media": media}
    return render(request, "base/media_detail.html", context)


@login_required
def media_edit(request, pk=None):
    media = get_object_or_404(Media, pk=pk) if pk else None
    if request.method == "POST":
        before_contributor_ids = set()
        if media is not None:
            before_contributor_ids = set(media.contributors.values_list("pk", flat=True))
        # Handle new contributors first
        new_contributor_names = request.POST.getlist("new_contributors")
        new_contributor_ids = []
        for raw_name in new_contributor_names:
            name = raw_name.strip()
            if name:
                agent, _created = Agent.objects.get_or_create(name=name)
                new_contributor_ids.append(str(agent.pk))

        # Create a mutable copy of POST data
        post_data = request.POST.copy()

        # Add new contributor IDs to existing contributors
        existing_contributors = post_data.getlist("contributors")
        all_contributor_ids = existing_contributors + new_contributor_ids
        post_data.setlist("contributors", all_contributor_ids)

        form = MediaForm(post_data, request.FILES, instance=media)
        if form.is_valid():
            instance = form.save()
            # Cleanup agents removed from this media that became orphans
            after_contributor_ids = set(instance.contributors.values_list("pk", flat=True))
            removed_ids = before_contributor_ids - after_contributor_ids
            if removed_ids:
                delete_orphan_agents_by_ids(removed_ids)

            # Add success message
            if media:
                messages.success(request, _("'%(title)s' updated successfully") % {"title": instance.title})
            else:
                messages.success(request, _("'%(title)s' created successfully") % {"title": instance.title})

            return redirect("media_detail", pk=instance.pk)
    else:
        form = MediaForm(instance=media)
    context = {"media": media, "form": form}
    return render(request, "base/media_edit.html", context)


@login_required
def media_delete(request, pk):
    media = get_object_or_404(Media, pk=pk)
    if request.method == "POST":
        # Memorise title before deletion
        media_title = media.title
        # Memorise contributors to cleanup after deletion
        contributor_ids = list(media.contributors.values_list("pk", flat=True))
        media.delete()
        delete_orphan_agents_by_ids(contributor_ids)

        # Add success message
        messages.success(request, _("'%(title)s' deleted successfully") % {"title": media_title})

        return redirect("home")
    return redirect("media_edit", pk=pk)


@login_required
def load_more_media(request):
    """HTMX view: load next page of media items for infinite scrolling."""
    context = build_media_context(request)

    # Return only the items + load more button
    return render(request, "partials/media_items/media_list_page.html", context)


@login_required
def agent_search_htmx(request):
    query = request.GET.get("q", "").strip()
    agents = Agent.objects.filter(name__icontains=query).order_by("name")[:12] if query else []
    return render(request, "partials/contributors/contributors_suggestions.html", {"agents": agents})


@login_required
def agent_select_htmx(request):
    """Select an existing agent and return the chip"""
    agent_id = request.POST.get("id")
    try:
        agent = Agent.objects.get(pk=agent_id)
        return render(request, "partials/contributors/contributor_chip.html", {"agent": agent})
    except Agent.DoesNotExist:
        return render(
            request, "partials/contributors/contributor_chip.html", {"agent": None, "error": "Agent not found"}
        )


@login_required
def media_review_clamped_htmx(request, pk):
    """HTMX view: return clamped review for a media item (for table cell collapse)."""
    media = get_object_or_404(Media, pk=pk)
    return render(request, "partials/media_items/media_review_clamped.html", {"media": media})


@login_required
def media_review_full_htmx(request, pk):
    """HTMX view: return full review for a media item (for table cell expansion)."""
    media = get_object_or_404(Media, pk=pk)
    return render(request, "partials/media_items/media_review_full.html", {"media": media})


@login_required
def backup_export(request):
    """Export backup and download it."""
    try:
        backup_path = create_backup()

        # Return the file as a download
        # FileResponse accepts a file object and handles closing it
        return FileResponse(
            backup_path.open("rb"),
            as_attachment=True,
            filename=backup_path.name,
        )

    except (OSError, tarfile.TarError, PermissionError) as e:
        messages.error(request, _("Backup creation failed: %(error)s") % {"error": str(e)})
        return redirect("backup_manage")


@login_required
def backup_import(request):
    """Import a backup file (with warning)."""
    if request.method == "POST":
        backup_file = request.FILES.get("backup_file")

        if not backup_file:
            messages.error(request, _("No file selected"))
            return redirect("backup_manage")

        if not backup_file.name.endswith(".tar.gz"):
            messages.error(request, _("Invalid file format. Use a .tar.gz file"))
            return redirect("backup_manage")

        tmp_path = None
        try:
            # Save the uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp_file:
                for chunk in backup_file.chunks():
                    tmp_file.write(chunk)
                tmp_path = tmp_file.name

            try:
                # Import the backup with --flush (delete existing data)
                call_command("import_backup", tmp_path, "--flush", verbosity=1)

                messages.success(request, _("Backup imported successfully! All data has been restored."))
                return redirect("home")

            finally:
                # Clean up temp file (always executed, even on exception)
                if tmp_path:
                    Path(tmp_path).unlink(missing_ok=True)

        except (OSError, CommandError, tarfile.TarError) as e:
            messages.error(request, _("Backup import failed: %(error)s") % {"error": str(e)})
            return redirect("backup_manage")

    return redirect("backup_manage")


@login_required
def backup_manage(request):
    """Display backup management page."""
    return render(request, "base/backup_manage.html")


def validate_saved_view_data(post_data):  # noqa: C901, PLR0912
    """
    Validate saved view data against model constraints.

    Args:
        post_data: POST data dictionary from request

    Returns:
        list: List of error messages (empty if valid)
    """
    errors = []

    # Validate media types against model choices
    valid_types = [choice[0] for choice in Media.media_type.field.choices]
    invalid_types = [t for t in post_data.getlist("type") if t not in valid_types]
    if invalid_types:
        errors.append(_("Invalid media types: %(types)s") % {"types": ", ".join(invalid_types)})

    # Validate statuses against model choices
    valid_statuses = [choice[0] for choice in Media.status.field.choices]
    invalid_statuses = [s for s in post_data.getlist("status") if s not in valid_statuses]
    if invalid_statuses:
        errors.append(_("Invalid statuses: %(statuses)s") % {"statuses": ", ".join(invalid_statuses)})

    # Validate scores against model choices + "none"
    valid_scores = [str(choice[0]) for choice in Media.score.field.choices] + ["none"]
    invalid_scores = [s for s in post_data.getlist("score") if s not in valid_scores]
    if invalid_scores:
        errors.append(_("Invalid scores: %(scores)s") % {"scores": ", ".join(invalid_scores)})

    # Validate sort field against whitelist
    sort = post_data.get("sort", "-review_date").lstrip("-")
    valid_sorts = {"created_at", "updated_at", "review_date", "score"}
    if sort not in valid_sorts:
        errors.append(_("Invalid sort field: %(sort)s") % {"sort": sort})

    # Validate view_mode against expected values
    view_mode = post_data.get("view_mode", "grid")
    valid_view_modes = {"grid", "list"}
    if view_mode not in valid_view_modes:
        errors.append(_("Invalid view mode: %(mode)s") % {"mode": view_mode})

    # Validate contributor (if present)
    contributor_id = post_data.get("contributor")
    if contributor_id:
        try:
            contributor_id_int = int(contributor_id)
            if not Agent.objects.filter(pk=contributor_id_int).exists():
                errors.append(_("Contributor does not exist: ID %(id)s") % {"id": contributor_id})
        except (ValueError, TypeError):
            errors.append(_("Invalid contributor ID format: %(id)s") % {"id": contributor_id})

    # Validate review dates (if present)
    for field_name, field_label in [("review_from", _("Start date")), ("review_to", _("End date"))]:
        date_value = post_data.get(field_name, "").strip()
        if date_value:
            try:
                PartialDate(date_value)
            except (ValueError, TypeError, DjangoValidationError):
                errors.append(_("Invalid %(label)s: %(value)s") % {"label": field_label, "value": date_value})

    # Validate has_review and has_cover
    for field_name, field_label in [("has_review", _("Review filter")), ("has_cover", _("Cover filter"))]:
        field_value = post_data.get(field_name, "")
        if field_value and field_value not in {"empty", "filled"}:
            errors.append(_("Invalid %(label)s value: %(value)s") % {"label": field_label, "value": field_value})

    return errors


@login_required
def saved_view_save(request):
    """Save or update a saved view."""
    if request.method != "POST":
        return redirect("home")

    view_name = request.POST.get("view_name", "").strip()

    if not view_name:
        messages.error(request, _("View name is required"))
        return redirect("home")

    # Validate all filter inputs before saving
    validation_errors = validate_saved_view_data(request.POST)
    if validation_errors:
        for error in validation_errors:
            messages.error(request, error)
        return redirect("home")

    # Extract current view state from request
    view_data = {
        "name": view_name,
        "filter_types": request.POST.getlist("type"),
        "filter_statuses": request.POST.getlist("status"),
        "filter_scores": request.POST.getlist("score"),
        "filter_contributor_id": request.POST.get("contributor") or None,
        "filter_review_from": request.POST.get("review_from", ""),
        "filter_review_to": request.POST.get("review_to", ""),
        "filter_has_review": request.POST.get("has_review", ""),
        "filter_has_cover": request.POST.get("has_cover", ""),
        "sort": request.POST.get("sort", "-review_date"),
        "view_mode": request.POST.get("view_mode", "grid"),
    }

    # Check if a view with this name already exists
    existing_view = SavedView.objects.filter(user=request.user, name=view_name).first()
    if existing_view:
        # Update the existing view instead of creating a new one
        for key, value in view_data.items():
            setattr(existing_view, key, value)
        existing_view.save()
        saved_view = existing_view
        messages.success(
            request,
            _("View '%(name)s' has been updated") % {"name": view_name},
        )
    else:
        # Create new view
        saved_view = SavedView.objects.create(user=request.user, **view_data)
        messages.success(request, _("View '%(name)s' saved successfully") % {"name": view_name})

    # Redirect to home with the view's filters applied
    return redirect(saved_view.get_filter_url())


@login_required
def saved_view_delete(request, pk):
    """Delete a saved view."""
    if request.method != "POST":
        return redirect("home")

    try:
        saved_view = SavedView.objects.get(pk=pk, user=request.user)
        view_name = saved_view.name
        saved_view.delete()
        messages.success(request, _("View '%(name)s' deleted successfully") % {"name": view_name})
    except SavedView.DoesNotExist:
        messages.error(request, _("View not found"))

    # Redirect to home to refresh the sidebar
    return redirect("home")
