import tarfile
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import MediaForm
from .models import Agent, Media
from .utils import create_backup, delete_orphan_agents_by_ids


def _resolve_sorting(request):
    """Return validated sorting info: selected field, sort string (with sign), and ordering."""
    default_field = "created_at"
    sort = request.GET.get("sort") or request.GET.get("order_by") or f"-{default_field}"

    raw_field = sort.lstrip("-")
    valid_fields = {"created_at", "review_date", "score"}
    sort_field = raw_field if raw_field in valid_fields else default_field

    is_desc = sort.startswith("-")
    ordering = f"-{sort_field}" if is_desc else sort_field
    normalized_sort = ordering  # ensure field is validated
    return sort_field, normalized_sort, ordering


def _extract_filters(request):
    """Extract filter parameters from request and return filters dict."""
    filters = {
        "contributor": request.GET.get("contributor", ""),
        "type": request.GET.get("type", ""),
        "status": request.GET.get("status", ""),
        "score": request.GET.get("score", ""),
        "review_from": request.GET.get("review_from", ""),
        "review_to": request.GET.get("review_to", ""),
    }
    filters["has_any"] = any(
        [
            filters["type"],
            filters["status"],
            filters["score"],
            filters["review_from"],
            filters["review_to"],
        ]
    )
    return filters


def _get_field_choices():
    """Return choices for filter fields from the Media model."""
    return {
        "media_type_choices": Media.media_type.field.choices,
        "status_choices": Media.status.field.choices,
        "score_choices": Media.score.field.choices,
    }


def _apply_filters(queryset, filters):
    """Apply filters to a queryset and return (queryset, contributor)."""
    contributor = None
    if filters["contributor"]:
        contributor = Agent.objects.filter(pk=filters["contributor"]).first()
        if contributor:
            queryset = queryset.filter(contributors=contributor)
    if filters["type"]:
        queryset = queryset.filter(media_type=filters["type"])
    if filters["status"]:
        queryset = queryset.filter(status=filters["status"])
    if filters["score"]:
        if filters["score"] == "none":
            queryset = queryset.filter(score__isnull=True)
        else:
            queryset = queryset.filter(score=int(filters["score"]))
    if filters["review_from"]:
        queryset = queryset.filter(review_date__gte=filters["review_from"])
    if filters["review_to"]:
        queryset = queryset.filter(review_date__lte=filters["review_to"])
    return queryset, contributor


@login_required
def index(request):
    """Main view for displaying media list."""
    # Get query parameters
    view_mode = request.GET.get("view_mode", "list")  # 'list' or 'grid'
    sort_field, sort, ordering = _resolve_sorting(request)
    filters = _extract_filters(request)

    queryset = Media.objects.order_by(ordering)
    queryset, contributor = _apply_filters(queryset, filters)

    context = {
        "media_list": queryset,
        "view_mode": view_mode,
        "order_by": ordering,
        "sort_field": sort_field,
        "sort": sort,
        "contributor": contributor,
        "filters": filters,
        **_get_field_choices(),
    }

    # If it's an HTMX request (filters/sorting), return the full list
    if request.headers.get("HX-Request"):
        return render(request, "partials/media-list.html", context)

    return render(request, "media.html", context)


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
                agent, _ = Agent.objects.get_or_create(name=name)
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
            return redirect("home")
    else:
        form = MediaForm(instance=media)
    context = {"media": media, "form": form}
    return render(request, "media_edit.html", context)


@login_required
def media_delete(request, pk):
    media = get_object_or_404(Media, pk=pk)
    if request.method == "POST":
        # Memorise contributors to cleanup after deletion
        contributor_ids = list(media.contributors.values_list("pk", flat=True))
        media.delete()
        delete_orphan_agents_by_ids(contributor_ids)
        return redirect("home")
    return redirect("media_edit", pk=pk)


@login_required
def search_media(request):
    query = request.GET.get("search", "")
    view_mode = request.GET.get("view_mode", "list")
    sort_field, sort, ordering = _resolve_sorting(request)
    filters = _extract_filters(request)

    media = Media.objects.filter(
        Q(title__icontains=query)
        | Q(contributors__name__icontains=query)
        | Q(pub_year__icontains=query)
        | Q(review__icontains=query),
    ).distinct()

    media, contributor = _apply_filters(media, filters)
    media = media.order_by(ordering)

    context = {
        "media_list": media,
        "view_mode": view_mode,
        "order_by": ordering,
        "sort_field": sort_field,
        "sort": sort,
        "contributor": contributor,
        "filters": filters,
        **_get_field_choices(),
    }
    return render(request, "partials/media-list.html", context)


@login_required
def agent_search_htmx(request):
    query = request.GET.get("q", "").strip()
    agents = Agent.objects.filter(name__icontains=query).order_by("name")[:12] if query else []
    return render(request, "partials/contributors-suggestions.html", {"agents": agents})


@login_required
def agent_select_htmx(request):
    """Select an existing agent and return the chip"""
    agent_id = request.POST.get("id")
    try:
        agent = Agent.objects.get(pk=agent_id)
        return render(request, "partials/contributor-chip.html", {"agent": agent})
    except Agent.DoesNotExist:
        return render(request, "partials/contributor-chip.html", {"agent": None, "error": "Agent not found"})


@login_required
def media_review_clamped_htmx(request, pk):
    """HTMX view: return clamped review for a media item (for table cell collapse)."""
    media = get_object_or_404(Media, pk=pk)
    return render(request, "partials/media-review-clamped.html", {"media": media})


@login_required
def media_review_full_htmx(request, pk):
    """HTMX view: return full review for a media item (for table cell expansion)."""
    media = get_object_or_404(Media, pk=pk)
    return render(request, "partials/media-review-full.html", {"media": media})


@login_required
def media_update_score_htmx(request, pk):
    """HTMX view: update media score and return updated score widget."""
    media = get_object_or_404(Media, pk=pk)

    if request.method == "POST":
        score_value = request.POST.get("score", "").strip()

        # Handle empty score (clear)
        if score_value == "":
            media.score = None
            media.save()
        else:
            try:
                score = int(score_value)
                # Validate that score is one of the valid choices
                valid_scores = dict(Media.score.field.choices).keys()
                if score in valid_scores:
                    media.score = score
                    media.save()
            except ValueError:
                # Invalid score format, don't update
                pass

    return render(request, "partials/score-editable.html", {"media": media})


@login_required
def media_update_status_htmx(request, pk):
    """HTMX view: update media status and return updated status widget."""
    media = get_object_or_404(Media, pk=pk)

    if request.method == "POST":
        status_value = request.POST.get("status", "").strip()

        # Validate that status is one of the valid choices
        valid_statuses = dict(Media.status.field.choices).keys()
        if status_value in valid_statuses:
            media.status = status_value
            media.save()

    context = {
        "media": media,
        "status_choices": Media.status.field.choices,
    }
    return render(request, "partials/status-editable.html", context)


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
    return render(request, "backup_manage.html")
