from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MediaForm
from .models import Agent, Media


@login_required
def index(request):
    media_list = Media.objects.all().order_by("-created_at")
    context = {"media_list": media_list}
    return render(request, "media.html", context)


@login_required
def media(request):
    media_list = Media.objects.all().order_by("-created_at")
    context = {"media_list": media_list}
    return render(request, "media.html", context)


@login_required
def media_edit(request, pk=None):
    media = get_object_or_404(Media, pk=pk)
    if request.method == "POST":
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
            form.save()
            return redirect("home")
    else:
        form = MediaForm(instance=media)
    context = {"media": media, "form": form}
    return render(request, "media_edit.html", context)


@login_required
def agent(request, pk=None):
    agent = get_object_or_404(Agent, pk=pk)
    context = {"agent": agent}
    return render(request, "agent.html", context)


@login_required
def search_media(request):
    query = request.GET.get("search", "")

    media = Media.objects.filter(
        Q(title__icontains=query)
        | Q(contributors__name__icontains=query)
        | Q(pub_year__icontains=query)
        | Q(review__icontains=query),
    )

    return render(request, "partials/media-list.html", {"media_list": media})


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
