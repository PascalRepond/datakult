import time

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Agent, Media


def index(request):
    return render(request, "home.html")


@login_required
def media(request):
    media_list = Media.objects.all().order_by("-created_at")
    context = {"media_list": media_list}
    return render(request, "media.html", context)


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

    return render(render, "partials/media-list.html", {"media_list": media})
