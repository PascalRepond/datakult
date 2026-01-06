import tarfile
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import MediaForm
from .models import Agent, Media
from .queries import build_media_context
from .utils import create_backup, delete_orphan_agents_by_ids


@login_required
def index(request):
    """Main view for displaying media list."""
    context = build_media_context(request)
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
    context = build_media_context(request)

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
