import logging
import tarfile
import tempfile
from pathlib import Path

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from partial_date import PartialDate

from .forms import MediaForm
from .models import Agent, Media, SavedView, Tag
from .queries import build_media_context
from .services.igdb import get_igdb_client
from .services.musicbrainz import get_musicbrainz_client
from .services.openlibrary import get_openlibrary_client
from .services.tmdb import get_tmdb_client
from .utils import create_backup, delete_orphan_agents_by_ids

logger = logging.getLogger(__name__)

# Search constants
DEFAULT_TMDB_LANGUAGE = "en-US"
MIN_SEARCH_QUERY_LENGTH = 2
MAX_SEARCH_RESULTS = 15


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


MAX_NAME_LENGTH = 100


def _get_or_create_safe(model_class, name):
    """
    Safely get or create an object by name with validation.

    Returns (instance, error_message). If error_message is not None,
    instance will be None.
    """
    clean_name = name.strip()[:MAX_NAME_LENGTH]

    if not clean_name:
        return None, None  # Skip empty names silently

    # Try to find existing object first to avoid race conditions
    existing = model_class.objects.filter(name=clean_name).first()
    if existing:
        return existing, None

    # Try to create, catching IntegrityError for race conditions
    try:
        obj, _created = model_class.objects.get_or_create(name=clean_name)
    except IntegrityError:
        # Race condition: object was created between filter() and get_or_create()
        existing = model_class.objects.filter(name=clean_name).first()
        if existing:
            return existing, None
        # Unexpected error
        return None, f"Failed to create {model_class.__name__}: {clean_name}"
    else:
        return obj, None


def _process_new_contributors(post_data):
    """Process new contributors from POST and return (modified POST data, errors)."""
    new_contributor_names = post_data.getlist("new_contributors")
    new_contributor_ids = []
    errors = []

    for raw_name in new_contributor_names:
        agent, error = _get_or_create_safe(Agent, raw_name)
        if error:
            errors.append(error)
        elif agent:
            new_contributor_ids.append(str(agent.pk))

    # Create a mutable copy and merge contributors
    post_data = post_data.copy()
    existing_contributors = post_data.getlist("contributors")
    post_data.setlist("contributors", existing_contributors + new_contributor_ids)
    return post_data, errors


def _process_new_tags(post_data):
    """Process new tags from POST and return (modified POST data, errors)."""
    new_tag_names = post_data.getlist("new_tags")
    new_tag_ids = []
    errors = []

    for raw_name in new_tag_names:
        tag, error = _get_or_create_safe(Tag, raw_name)
        if error:
            errors.append(error)
        elif tag:
            new_tag_ids.append(str(tag.pk))

    # Merge with existing tags
    existing_tags = post_data.getlist("tags")
    post_data.setlist("tags", existing_tags + new_tag_ids)
    return post_data, errors


def _handle_import_cover(request, instance):
    """Download and attach cover from import source if provided."""
    cover_url = request.POST.get("import_cover_url")
    if cover_url and not request.FILES.get("cover"):
        cover_bytes = _download_cover(cover_url)
        if cover_bytes:
            filename = f"{instance.title[:50].replace('/', '_')}.jpg"
            instance.cover.save(filename, ContentFile(cover_bytes), save=False)


def _download_cover(cover_url: str) -> bytes | None:
    """Download cover image from any supported source."""
    if not cover_url:
        return None

    # Determine source and use appropriate client
    if "image.tmdb.org" in cover_url:
        client = get_tmdb_client()
        if client:
            return client.download_cover(cover_url)
    elif "images.igdb.com" in cover_url:
        client = get_igdb_client()
        if client:
            return client.download_cover(cover_url)
    elif "covers.openlibrary.org" in cover_url:
        client = get_openlibrary_client()
        return client.download_cover(cover_url)
    elif "coverartarchive.org" in cover_url:
        client = get_musicbrainz_client()
        return client.download_cover(cover_url)

    return None


def _build_import_initial_data(import_data: dict, media=None) -> dict:
    """Build form initial data from import data, optionally merging with existing media."""
    # Determine media_type based on source
    source_media_type = import_data.get("media_type", "")
    if source_media_type == "movie":
        media_type = "FILM"
    elif source_media_type == "tv":
        media_type = "TV"
    elif source_media_type == "game":
        media_type = "GAME"
    elif source_media_type == "book":
        media_type = "BOOK"
    elif source_media_type == "music":
        media_type = "MUSIC"
    else:
        media_type = ""

    # Determine external URI
    external_uri = (
        import_data.get("tmdb_url")
        or import_data.get("igdb_url")
        or import_data.get("openlibrary_url")
        or import_data.get("musicbrainz_url")
        or ""
    )

    initial_data = {
        "title": import_data.get("title", ""),
        "pub_year": import_data.get("year"),
        "media_type": media_type,
        "external_uri": external_uri,
    }
    if media:
        # Keep existing values for fields user may have customized
        initial_data["status"] = media.status
        initial_data["score"] = media.score
        initial_data["review"] = media.review
        initial_data["review_date"] = media.review_date
    return initial_data


def _get_import_data_from_request(request) -> dict | None:
    """Fetch import data based on request parameters."""
    tmdb_id = request.GET.get("tmdb_id")
    media_type = request.GET.get("media_type")
    lang = request.GET.get("lang", DEFAULT_TMDB_LANGUAGE)
    igdb_id = request.GET.get("igdb_id")
    openlibrary_key = request.GET.get("openlibrary_key")
    musicbrainz_id = request.GET.get("musicbrainz_id")

    if tmdb_id and media_type in ("movie", "tv"):
        return _fetch_tmdb_data(tmdb_id, media_type, language=lang)
    if igdb_id:
        return _fetch_igdb_data(igdb_id)
    if openlibrary_key:
        openlibrary_year = request.GET.get("year")
        year = int(openlibrary_year) if openlibrary_year and openlibrary_year.isdigit() else None
        return _fetch_openlibrary_data(openlibrary_key, year=year)
    if musicbrainz_id:
        return _fetch_musicbrainz_data(musicbrainz_id)
    return None


@login_required
def media_edit(request, pk=None):
    media = get_object_or_404(Media, pk=pk) if pk else None
    import_data = None
    import_contributors = []
    import_tags = []

    if request.method == "POST":
        before_contributor_ids = set(media.contributors.values_list("pk", flat=True)) if media else set()
        post_data, contributor_errors = _process_new_contributors(request.POST)
        post_data, tag_errors = _process_new_tags(post_data)

        # Report any errors from processing contributors/tags
        for error in contributor_errors + tag_errors:
            messages.error(request, error)

        form = MediaForm(post_data, request.FILES, instance=media)
        if form.is_valid():
            instance = form.save(commit=False)
            _handle_import_cover(request, instance)
            instance.save()
            form.save_m2m()

            # Cleanup orphan agents
            after_contributor_ids = set(instance.contributors.values_list("pk", flat=True))
            removed_ids = before_contributor_ids - after_contributor_ids
            if removed_ids:
                delete_orphan_agents_by_ids(removed_ids)

            msg_key = "'%(title)s' updated successfully" if media else "'%(title)s' created successfully"
            messages.success(request, _(msg_key) % {"title": instance.title})
            return redirect("media_detail", pk=instance.pk)
    else:
        import_data = _get_import_data_from_request(request)
        if import_data:
            initial_data = _build_import_initial_data(import_data, media)
            form = MediaForm(initial=initial_data, instance=media)

            # Filter out contributors/tags that already exist on the media
            existing_contributor_names = set()
            existing_tag_names = set()
            if media:
                existing_contributor_names = {c.name.lower() for c in media.contributors.all()}
                existing_tag_names = {t.name.lower() for t in media.tags.all()}

            import_contributors = [
                name for name in import_data.get("contributors", []) if name.lower() not in existing_contributor_names
            ]
            import_tags = [name for name in import_data.get("genres", []) if name.lower() not in existing_tag_names]
        else:
            form = MediaForm(instance=media)

    context = {
        "media": media,
        "form": form,
        "import_data": import_data,
        "import_contributors": import_contributors,
        "import_tags": import_tags,
    }
    return render(request, "base/media_edit.html", context)


def _fetch_tmdb_data(tmdb_id: str, media_type: str, language: str = DEFAULT_TMDB_LANGUAGE) -> dict | None:
    """Fetch TMDB data for pre-filling the form."""
    client = get_tmdb_client()
    if not client:
        return None

    try:
        details = client.get_full_details(int(tmdb_id), media_type, language=language)
    except (requests.RequestException, ValueError):
        logger.exception("Failed to fetch TMDB data for %s/%s", media_type, tmdb_id)
        return None

    # Combine directors and production companies
    contributors = details.get("directors", []) + details.get("production_companies", [])
    details["contributors"] = contributors
    return details


def _fetch_igdb_data(igdb_id: str) -> dict | None:
    """Fetch IGDB data for pre-filling the form."""
    client = get_igdb_client()
    if not client:
        return None

    try:
        details = client.get_game_details(int(igdb_id))
    except (requests.RequestException, ValueError):
        logger.exception("Failed to fetch IGDB data for game %s", igdb_id)
        return None

    return details


def _fetch_openlibrary_data(work_key: str, year: int | None = None) -> dict | None:
    """Fetch OpenLibrary data for pre-filling the form."""
    client = get_openlibrary_client()

    try:
        details = client.get_work_details(work_key, first_publish_year=year)
    except requests.RequestException:
        logger.exception("Failed to fetch OpenLibrary data for work %s", work_key)
        return None

    return details


def _fetch_musicbrainz_data(mbid: str) -> dict | None:
    """Fetch MusicBrainz data for pre-filling the form."""
    client = get_musicbrainz_client()

    try:
        details = client.get_release_details(mbid)
    except requests.RequestException:
        logger.exception("Failed to fetch MusicBrainz data for release %s", mbid)
        return None

    return details


@login_required
def media_import(request):
    """Display TMDB search page for importing media."""
    # Optional: if editing existing media, pass media_id to template
    media_id = request.GET.get("media_id")
    context = {"media_id": media_id}
    return render(request, "base/media_import.html", context)


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
def tag_search_htmx(request):
    """HTMX view: search tags by name."""
    query = request.GET.get("q", "").strip()
    tags = Tag.objects.filter(name__icontains=query).order_by("name")[:12] if query else []
    return render(request, "partials/tags/tag_suggestions.html", {"tags": tags})


@login_required
def tag_select_htmx(request):
    """Select an existing tag and return the chip."""
    tag_id = request.POST.get("id")
    try:
        tag = Tag.objects.get(pk=tag_id)
        return render(request, "partials/tags/tag_chip.html", {"tag": tag})
    except Tag.DoesNotExist:
        return render(request, "partials/tags/tag_chip.html", {"tag": None, "error": "Tag not found"})


@login_required
def tmdb_search_htmx(request):
    """HTMX view: search TMDB for movies and TV shows."""
    query = request.GET.get("q", "").strip()
    media_id = request.GET.get("media_id")  # For editing existing media
    lang = request.GET.get("lang", DEFAULT_TMDB_LANGUAGE)

    base_context = {"results": [], "media_id": media_id, "lang": lang, "query": query}

    if len(query) < MIN_SEARCH_QUERY_LENGTH:
        return render(request, "partials/tmdb/tmdb_suggestions.html", base_context)

    client = get_tmdb_client()
    if not client:
        logger.warning("TMDB search attempted but API key not configured")
        return render(
            request,
            "partials/tmdb/tmdb_suggestions.html",
            {**base_context, "error": "TMDB API key not configured"},
        )

    try:
        results = client.search_multi(query, language=lang)[:MAX_SEARCH_RESULTS]
    except requests.RequestException:
        logger.exception("TMDB search failed")
        return render(
            request,
            "partials/tmdb/tmdb_suggestions.html",
            {**base_context, "error": "Search failed"},
        )

    return render(request, "partials/tmdb/tmdb_suggestions.html", {**base_context, "results": results})


@login_required
def igdb_search_htmx(request):
    """HTMX view: search IGDB for video games."""
    query = request.GET.get("q", "").strip()
    media_id = request.GET.get("media_id")

    base_context = {"results": [], "media_id": media_id, "query": query}

    if len(query) < MIN_SEARCH_QUERY_LENGTH:
        return render(request, "partials/igdb/igdb_suggestions.html", base_context)

    client = get_igdb_client()
    if not client:
        logger.warning("IGDB search attempted but API credentials not configured")
        return render(
            request,
            "partials/igdb/igdb_suggestions.html",
            {**base_context, "error": "IGDB API credentials not configured"},
        )

    try:
        results = client.search_games(query, limit=MAX_SEARCH_RESULTS)
    except requests.RequestException:
        logger.exception("IGDB search failed")
        return render(
            request,
            "partials/igdb/igdb_suggestions.html",
            {**base_context, "error": "Search failed"},
        )

    return render(request, "partials/igdb/igdb_suggestions.html", {**base_context, "results": results})


@login_required
def openlibrary_search_htmx(request):
    """HTMX view: search OpenLibrary for books."""
    query = request.GET.get("q", "").strip()
    media_id = request.GET.get("media_id")

    base_context = {"results": [], "media_id": media_id, "query": query}

    if len(query) < MIN_SEARCH_QUERY_LENGTH:
        return render(request, "partials/openlibrary/openlibrary_suggestions.html", base_context)

    client = get_openlibrary_client()

    try:
        results = client.search_books(query, limit=MAX_SEARCH_RESULTS)
    except requests.RequestException:
        logger.exception("OpenLibrary search failed")
        return render(
            request,
            "partials/openlibrary/openlibrary_suggestions.html",
            {**base_context, "error": "Search failed"},
        )

    return render(request, "partials/openlibrary/openlibrary_suggestions.html", {**base_context, "results": results})


@login_required
def musicbrainz_search_htmx(request):
    """HTMX view: search MusicBrainz for music albums."""
    query = request.GET.get("q", "").strip()
    media_id = request.GET.get("media_id")

    base_context = {"results": [], "media_id": media_id, "query": query}

    if len(query) < MIN_SEARCH_QUERY_LENGTH:
        return render(request, "partials/musicbrainz/musicbrainz_suggestions.html", base_context)

    client = get_musicbrainz_client()

    try:
        results = client.search_releases(query, limit=MAX_SEARCH_RESULTS)
    except requests.RequestException:
        logger.exception("MusicBrainz search failed")
        return render(
            request,
            "partials/musicbrainz/musicbrainz_suggestions.html",
            {**base_context, "error": "Search failed"},
        )

    return render(request, "partials/musicbrainz/musicbrainz_suggestions.html", {**base_context, "results": results})


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
