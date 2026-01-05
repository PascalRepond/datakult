import contextlib
import tarfile
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import MediaForm
from .models import Agent, Media
from .utils import create_backup, delete_orphan_agents_by_ids


def _resolve_sorting(request):
    """Return validated sorting info: selected field and normalized sort string (with sign)."""
    default_field = "review_date"
    sort = request.GET.get("sort") or request.GET.get("order_by") or f"-{default_field}"

    raw_field = sort.lstrip("-")
    valid_fields = {"created_at", "review_date", "score"}
    sort_field = raw_field if raw_field in valid_fields else default_field

    is_desc = sort.startswith("-")
    normalized_sort = f"-{sort_field}" if is_desc else sort_field
    return sort_field, normalized_sort


def _extract_filters(request):
    """Extract filter parameters from request and return filters dict."""
    filters = {
        "contributor": request.GET.get("contributor", ""),
        "type": request.GET.getlist("type"),
        "status": request.GET.getlist("status"),
        "score": request.GET.getlist("score"),
        "review_from": request.GET.get("review_from", ""),
        "review_to": request.GET.get("review_to", ""),
        "has_review": request.GET.get("has_review", ""),
        "has_cover": request.GET.get("has_cover", ""),
    }
    filters["has_any"] = any(
        [
            filters["type"],
            filters["status"],
            filters["score"],
            filters["review_from"],
            filters["review_to"],
            filters["has_review"],
            filters["has_cover"],
        ]
    )

    # Add display names for active filters (as list of tuples: (value, label))
    if filters["type"]:
        type_choices_dict = dict(Media.media_type.field.choices)
        filters["type_display"] = [(t, type_choices_dict.get(t, t)) for t in filters["type"]]
    if filters["status"]:
        status_choices_dict = dict(Media.status.field.choices)
        filters["status_display"] = [(s, status_choices_dict.get(s, s)) for s in filters["status"]]
    if filters["score"]:
        score_choices_dict = dict(Media.score.field.choices)
        filters["score_display"] = []
        for s in filters["score"]:
            if s == "none":
                filters["score_display"].append(("none", _("Not rated")))
            else:
                try:
                    filters["score_display"].append((s, score_choices_dict.get(int(s), s)))
                except ValueError:
                    # Skip malformed score values from URL
                    continue

    return filters


def _get_field_choices():
    """Return choices for filter fields from the Media model."""
    return {
        "media_type_choices": Media.media_type.field.choices,
        "status_choices": Media.status.field.choices,
        "score_choices": Media.score.field.choices,
    }


def _build_search_queryset(query):
    """Build a filtered queryset based on search query."""
    return Media.objects.filter(
        Q(title__icontains=query)
        | Q(contributors__name__icontains=query)
        | Q(pub_year__icontains=query)
        | Q(review__icontains=query),
    ).distinct()


def _apply_contributor_filter(queryset, contributor_id):
    """Apply contributor filter to queryset and return (queryset, contributor)."""
    contributor = None
    if contributor_id:
        contributor = Agent.objects.filter(pk=contributor_id).first()
        if contributor:
            queryset = queryset.filter(contributors=contributor)
    return queryset, contributor


def _apply_type_filter(queryset, media_types):
    """Apply OR filter for media types."""
    if not media_types:
        return queryset
    return queryset.filter(media_type__in=media_types)


def _apply_status_filter(queryset, statuses):
    """Apply OR filter for statuses."""
    if not statuses:
        return queryset
    return queryset.filter(status__in=statuses)


def _apply_score_filter(queryset, scores):
    """Apply OR filter for scores (including 'none' for null scores)."""
    if not scores:
        return queryset
    score_q = Q()
    for score in scores:
        if score == "none":
            score_q |= Q(score__isnull=True)
        else:
            try:
                score_q |= Q(score=int(score))
            except ValueError:
                # Skip malformed score values from URL
                continue
    return queryset.filter(score_q)


def _apply_date_and_content_filters(queryset, filters):
    """Apply review date, review content, and cover filters."""
    if filters["review_from"]:
        # Skip malformed date values from URL
        with contextlib.suppress(ValueError, TypeError, ValidationError):
            queryset = queryset.filter(review_date__gte=filters["review_from"])
    if filters["review_to"]:
        # Skip malformed date values from URL
        with contextlib.suppress(ValueError, TypeError, ValidationError):
            queryset = queryset.filter(review_date__lte=filters["review_to"])
    if filters["has_review"] == "empty":
        queryset = queryset.filter(Q(review__isnull=True) | Q(review=""))
    elif filters["has_review"] == "filled":
        queryset = queryset.exclude(Q(review__isnull=True) | Q(review=""))
    if filters["has_cover"] == "empty":
        queryset = queryset.filter(Q(cover__isnull=True) | Q(cover=""))
    elif filters["has_cover"] == "filled":
        queryset = queryset.exclude(Q(cover__isnull=True) | Q(cover=""))
    return queryset


def _apply_filters(queryset, filters):
    """Apply filters to a queryset and return (queryset, contributor)."""
    queryset, contributor = _apply_contributor_filter(queryset, filters["contributor"])
    queryset = _apply_type_filter(queryset, filters["type"])
    queryset = _apply_status_filter(queryset, filters["status"])
    queryset = _apply_score_filter(queryset, filters["score"])
    queryset = _apply_date_and_content_filters(queryset, filters)
    return queryset, contributor


def _build_media_context(request):
    """
    Build and filter media queryset from request parameters.

    Returns a tuple of (page_obj, context_dict) ready for rendering.
    This consolidates the common logic used by index and load_more_media views.
    """
    view_mode = request.GET.get("view_mode", "grid")
    sort_field, sort = _resolve_sorting(request)
    filters = _extract_filters(request)
    search_query = request.GET.get("search", "").strip()

    # Build queryset based on whether it's a search or not
    queryset = _build_search_queryset(search_query) if search_query else Media.objects.all()

    # Apply filters and sorting
    queryset, contributor = _apply_filters(queryset, filters)
    queryset = queryset.order_by(sort)

    # Pagination: 20 items per page
    page_number = request.GET.get("page", 1)
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(page_number)

    context = {
        "media_list": page_obj.object_list,
        "page_obj": page_obj,
        "view_mode": view_mode,
        "sort_field": sort_field,
        "sort": sort,
        "contributor": contributor,
        "filters": filters,
        **_get_field_choices(),
    }

    return page_obj, context


@login_required
def index(request):
    """Main view for displaying media list."""
    _, context = _build_media_context(request)
    return render(request, "media.html", context)


@login_required
def media_detail(request, pk):
    """Display detailed view of a single media item."""
    media = get_object_or_404(Media, pk=pk)
    context = {"media": media}
    return render(request, "media_detail.html", context)


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
            return redirect("media_detail", pk=instance.pk)
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
def load_more_media(request):
    """HTMX view: load next page of media items for infinite scrolling."""
    _, context = _build_media_context(request)

    # Return only the items + load more button
    return render(request, "partials/media-items-page.html", context)


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
