"""Views of the media list, of a media, of its form, and of the contributors and tags picked in it."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.forms import MediaForm
from core.htmx_validation import field_error_response
from core.models import Agent, Media, Tag
from core.queries import build_media_context
from core.utils import delete_orphan_agents_by_ids

from .imports import attach_import_cover, fetch_import_data, import_initial_data, import_suggestions

MAX_NAME_LENGTH = 100
MAX_SUGGESTIONS = 12


@login_required
def index(request):
    """Main view for displaying media list."""
    return render(request, "base/media_index.html", build_media_context(request))


@login_required
def load_more_media(request):
    """HTMX view: load next page of media items for infinite scrolling, without the rest of the page."""
    return render(request, "partials/media_items/media_list_page.html", build_media_context(request))


@login_required
def media_detail(request, pk):
    """Display detailed view of a single media item."""
    return render(request, "base/media_detail.html", {"media": get_object_or_404(Media, pk=pk)})


@login_required
def media_review_htmx(request, pk):
    """HTMX view: return the full review of a media item, for the reading modal of the media list."""
    media = get_object_or_404(Media, pk=pk)
    return render(request, "partials/media_items/media_review_modal.html", {"media": media})


def _get_or_create_safe(model_class, name):
    """
    Safely get or create an object by name with validation.

    Returns (instance, error_message). If error_message is not None,
    instance will be None.
    """
    clean_name = name.strip()[:MAX_NAME_LENGTH]

    if not clean_name:
        return None, None  # Skip empty names silently

    if existing := model_class.objects.filter(name=clean_name).first():
        return existing, None

    # Try to create, catching IntegrityError for race conditions
    try:
        obj, _created = model_class.objects.get_or_create(name=clean_name)
    except IntegrityError:
        if existing := model_class.objects.filter(name=clean_name).first():
            return existing, None
        # Unexpected error
        return None, f"Failed to create {model_class.__name__}: {clean_name}"
    else:
        return obj, None


def _with_new_related(post_data, field_name, model):
    """
    Return the form data with the objects named in its new_<field_name> list added to <field_name>, created if need be.

    Also return the errors of the names that could not be added.
    """
    new_ids, errors = [], []
    for raw_name in post_data.getlist(f"new_{field_name}"):
        obj, error = _get_or_create_safe(model, raw_name)
        if error:
            errors.append(error)
        elif obj:
            new_ids.append(str(obj.pk))

    post_data = post_data.copy()
    post_data.setlist(field_name, post_data.getlist(field_name) + new_ids)
    return post_data, errors


@login_required
def media_edit(request, pk=None):
    """Add a media, or edit one, filled with the metadata of an import source when the request names one."""
    media = get_object_or_404(Media, pk=pk) if pk else None
    import_data = None
    import_contributors = []
    import_tags = []

    if request.method == "POST":
        before_contributor_ids = set(media.contributors.values_list("pk", flat=True)) if media else set()
        post_data, contributor_errors = _with_new_related(request.POST, "contributors", Agent)
        post_data, tag_errors = _with_new_related(post_data, "tags", Tag)

        # Report any errors from processing contributors/tags
        for error in contributor_errors + tag_errors:
            messages.error(request, error)

        form = MediaForm(post_data, request.FILES, instance=media)
        if form.is_valid():
            instance = form.save(commit=False)
            attach_import_cover(request, instance)
            try:
                instance.save()
            except ValidationError as error:  # The cover, uploaded or imported, could not be compressed
                form.add_error("cover", error)
            else:
                form.save_m2m()

                # Cleanup orphan agents
                after_contributor_ids = set(instance.contributors.values_list("pk", flat=True))
                if removed_ids := before_contributor_ids - after_contributor_ids:
                    delete_orphan_agents_by_ids(removed_ids)

                msg_key = "'%(title)s' updated successfully" if media else "'%(title)s' created successfully"
                messages.success(request, _(msg_key) % {"title": instance.title})
                return redirect("media_detail", pk=instance.pk)
    elif import_data := fetch_import_data(request):
        form = MediaForm(initial=import_initial_data(import_data, media), instance=media)
        import_contributors, import_tags = import_suggestions(import_data, media)
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


@require_POST
@login_required
def validate_media_field(request):
    """HTMX view: validate a field of the media form while it is typed."""
    return field_error_response(MediaForm(request.POST, request.FILES), request.POST.get("field_name"))


@login_required
def media_delete(request, pk):
    """Delete a media, and the contributors it leaves without media."""
    media = get_object_or_404(Media, pk=pk)
    if request.method != "POST":
        return redirect("media_edit", pk=pk)

    # Memorise the contributors, to delete those left without media
    contributor_ids = list(media.contributors.values_list("pk", flat=True))
    media.delete()
    delete_orphan_agents_by_ids(contributor_ids)
    messages.success(request, _("'%(title)s' deleted successfully") % {"title": media.title})
    return redirect("home")


def _search_by_name(request, model, template, context_name):
    """Render the objects whose name holds the query, as suggestions."""
    query = request.GET.get("q", "").strip()
    found = model.objects.filter(name__icontains=query).order_by("name")[:MAX_SUGGESTIONS] if query else []
    return render(request, template, {context_name: found})


def _select_by_pk(request, model, template, context_name, not_found):
    """Render the chip of the picked object, or the `not_found` error when it does not exist."""
    try:
        return render(request, template, {context_name: model.objects.get(pk=request.POST.get("id"))})
    except model.DoesNotExist:
        return render(request, template, {context_name: None, "error": not_found})


@login_required
def agent_search_htmx(request):
    """HTMX view: search contributors by name."""
    return _search_by_name(request, Agent, "partials/contributors/contributors_suggestions.html", "agents")


@login_required
def agent_select_htmx(request):
    """HTMX view: return the chip of the picked contributor."""
    return _select_by_pk(request, Agent, "partials/contributors/contributor_chip.html", "agent", "Agent not found")


@login_required
def tag_search_htmx(request):
    """HTMX view: search tags by name."""
    return _search_by_name(request, Tag, "partials/tags/tag_suggestions.html", "tags")


@login_required
def tag_select_htmx(request):
    """HTMX view: return the chip of the picked tag."""
    return _select_by_pk(request, Tag, "partials/tags/tag_chip.html", "tag", "Tag not found")
