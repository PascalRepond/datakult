from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MediaForm
from .models import Agent, Media
from .utils import delete_orphan_agents_by_ids


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


@login_required
def index(request):
    """Main view for displaying media list."""
    # Get query parameters
    view_mode = request.GET.get("view_mode", "list")  # 'list' or 'grid'
    sort_field, sort, ordering = _resolve_sorting(request)

    queryset = Media.objects.order_by(ordering)

    context = {
        "media_list": queryset,
        "view_mode": view_mode,
        "order_by": ordering,
        "sort_field": sort_field,
        "sort": sort,
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
        # Memorize contributors to cleanup after deletion
        contributor_ids = list(media.contributors.values_list("pk", flat=True))
        media.delete()
        delete_orphan_agents_by_ids(contributor_ids)
        return redirect("home")
    return redirect("media_edit", pk=pk)


@login_required
def agent(request, pk=None):
    agent = get_object_or_404(Agent, pk=pk)
    context = {"agent": agent}
    return render(request, "agent.html", context)


@login_required
def search_media(request):
    query = request.GET.get("search", "")
    view_mode = request.GET.get("view_mode", "list")
    sort_field, sort, ordering = _resolve_sorting(request)

    media = Media.objects.filter(
        Q(title__icontains=query)
        | Q(contributors__name__icontains=query)
        | Q(pub_year__icontains=query)
        | Q(review__icontains=query),
    ).distinct()
    media = media.order_by(ordering)

    context = {
        "media_list": media,
        "view_mode": view_mode,
        "order_by": ordering,
        "sort_field": sort_field,
        "sort": sort,
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
