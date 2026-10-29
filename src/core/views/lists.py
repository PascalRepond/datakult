"""Views of the lists in which each user ranks media."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from core.forms import CustomListForm
from core.models import CustomList, ListEntry, Media
from core.queries import LIST_URL_SESSION_KEY, lists_for_media
from core.views.media import MAX_SUGGESTIONS

LISTS_PER_PAGE = 24
LIST_SORT_OPTIONS = [
    ("-updated_at", gettext_lazy("Recently updated")),
    ("name", gettext_lazy("Name (A-Z)")),
]
# Number of the first media of a list whose covers its card shows
CARD_COVERS = 4


def _render_entries(request, custom_list, template="partials/lists/list_entries.html", **context):
    """Render the media of a list in their order, as the list page shows them, with the rest of the context."""
    entries = custom_list.entries.select_related("media")
    return render(request, template, {"custom_list": custom_list, "entries": entries, **context})


def _get_posted_or_404(request, model, key, **filters):
    """Return the object whose ID the request posts under the key, raising Http404 when it is not a number."""
    pk = request.POST.get(key, "")
    if not pk.isdecimal():
        raise Http404
    return get_object_or_404(model, pk=pk, **filters)


def _lists_context(request):
    """Return the page of the lists of the user that match the search, in the order of the sort, and that sort."""
    search = request.GET.get("search", "").strip()
    sort = request.GET.get("sort")
    if sort not in dict(LIST_SORT_OPTIONS):
        sort = LIST_SORT_OPTIONS[0][0]

    lists = request.user.lists.annotate(media_count=Count("entries")).prefetch_related(
        Prefetch("entries", ListEntry.objects.select_related("media")[:CARD_COVERS], to_attr="first_entries")
    )
    if search:
        lists = lists.filter(Q(name__icontains=search) | Q(description__icontains=search))
    # Lists that tie come newest first, for their order to hold from one page to the next
    lists = lists.order_by(Lower("name") if sort == "name" else "-updated_at", "-pk")
    return {
        "page_obj": Paginator(lists, LISTS_PER_PAGE).get_page(request.GET.get("page")),
        "sort": sort,
        "sort_options": LIST_SORT_OPTIONS,
    }


@login_required
def list_index(request):
    """Display the lists of the user matching the search, with the form creating a new one."""
    # The template only asks whether the user has lists when none matches the search
    context = {**_lists_context(request), "has_lists": request.user.lists.exists, "form": CustomListForm()}
    return render(request, "base/list_index.html", context)


@login_required
def load_more_lists(request):
    """HTMX view: load the next page of lists for infinite scrolling, without the rest of the page."""
    return render(request, "partials/lists/list_cards_page.html", _lists_context(request))


@login_required
def list_detail(request, pk):
    """Display a list of the user with its media in their order, and the forms editing or deleting it."""
    custom_list = get_object_or_404(CustomList, pk=pk, user=request.user)
    # Remember the list for the ways back to it from its media
    request.session[LIST_URL_SESSION_KEY] = request.get_full_path()
    return _render_entries(request, custom_list, "base/list_detail.html", form=CustomListForm(instance=custom_list))


@login_required
def list_media_search(request, pk):
    """HTMX view: search the media to add to a list by title, among those it does not hold yet."""
    custom_list = get_object_or_404(CustomList, pk=pk, user=request.user)
    query = request.GET.get("q", "").strip()
    found = (
        Media.objects.filter(title__icontains=query).exclude(lists=custom_list).order_by("title")[:MAX_SUGGESTIONS]
        if query
        else []
    )
    context = {"custom_list": custom_list, "query": query, "found": found}
    return render(request, "partials/lists/list_media_suggestions.html", context)


@login_required
def list_edit(request, pk=None):
    """Create a list of the user, or update one of their lists, from the form of its dialog."""
    editing = pk is not None
    custom_list = get_object_or_404(CustomList, pk=pk, user=request.user) if editing else CustomList(user=request.user)
    # A new list is shown among the others, an updated one on its own page
    response = redirect("list_detail", pk=pk) if editing else redirect("list_index")
    if request.method != "POST":
        return response

    form = CustomListForm(request.POST, instance=custom_list)
    if form.is_valid():
        form.save()
        message = _("List '%(name)s' updated successfully") if editing else _("List '%(name)s' created successfully")
        messages.success(request, message % {"name": custom_list.name})
    else:
        # The dialog being closed, a single message gives the first error of the first invalid field
        field, errors = next(iter(form.errors.items()))
        messages.error(request, _("%(field)s: %(error)s") % {"field": form[field].label, "error": errors[0]})
    return response


@login_required
def list_delete(request, pk):
    """Delete a list of the user, leaving its media untouched."""
    custom_list = get_object_or_404(CustomList, pk=pk, user=request.user)
    if request.method != "POST":
        return redirect("list_detail", pk=pk)

    custom_list.delete()
    # The ways back no longer lead to the deleted list
    if request.session.get(LIST_URL_SESSION_KEY) == reverse("list_detail", args=[pk]):
        del request.session[LIST_URL_SESSION_KEY]
    messages.success(request, _("List '%(name)s' deleted successfully") % {"name": custom_list.name})
    return redirect("list_index")


@require_POST
@login_required
def list_entry_add(request, pk):
    """HTMX view: add a media at the end of a list, and return the media of the list with the search emptied."""
    custom_list = get_object_or_404(CustomList, pk=pk, user=request.user)
    custom_list.append(_get_posted_or_404(request, Media, "media"))
    return _render_entries(request, custom_list, "partials/lists/list_entry_added.html")


@require_POST
@login_required
def list_entry_remove(request, pk):
    """HTMX view: remove a media from its list, and return the media of the list."""
    entry = get_object_or_404(ListEntry, pk=pk, custom_list__user=request.user)
    entry.delete()
    return _render_entries(request, entry.custom_list)


@require_POST
@login_required
def list_entry_move(request, pk):
    """HTMX view: swap a media with the one above or below it in its list, and return the media of the list."""
    entry = get_object_or_404(ListEntry, pk=pk, custom_list__user=request.user)
    entries = entry.custom_list.entries
    if request.POST.get("direction") == "up":
        neighbour = entries.filter(position__lt=entry.position).last()
    else:
        neighbour = entries.filter(position__gt=entry.position).first()
    if neighbour:
        entry.position, neighbour.position = neighbour.position, entry.position
        ListEntry.objects.bulk_update([entry, neighbour], ["position"])
        entry.custom_list.touch()
    return _render_entries(request, entry.custom_list)


@require_POST
@login_required
def media_lists_htmx(request, pk):
    """HTMX view: put a media in a list of the user when its box is checked on the media page, or take it out."""
    media = get_object_or_404(Media, pk=pk)
    custom_list = _get_posted_or_404(request, CustomList, "list", user=request.user)
    # The box sends its value only while checked
    if request.POST.get("checked"):
        custom_list.append(media)
    else:
        custom_list.media.remove(media)
    return HttpResponse(status=204)


@login_required
def media_lists_search_htmx(request, pk):
    """HTMX view: search the lists of the user by name, for the menu of a media page."""
    media = get_object_or_404(Media, pk=pk)
    lists = lists_for_media(request.user, media, request.GET.get("q", "").strip())
    return render(request, "partials/lists/media_lists_options.html", {"media": media, "lists": lists})
