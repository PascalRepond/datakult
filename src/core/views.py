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
        form = MediaForm(request.POST, request.FILES, instance=media)
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
