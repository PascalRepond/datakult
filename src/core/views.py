from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

from core.models import Agent, Media
from core.serializers import AgentSerializer, MediaSerializer


@api_view(["GET"])
def api_root(request, format=None):
    return Response(
        {
            "agents": reverse("agent-list", request=request, format=format),
            "media": reverse("media-list", request=request, format=format),
        },
    )


class MediaViewset(viewsets.ModelViewSet):
    queryset = Media.objects.all()
    serializer_class = MediaSerializer


class AgentViewset(viewsets.ModelViewSet):
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
