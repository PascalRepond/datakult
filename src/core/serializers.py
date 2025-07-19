from rest_framework import serializers

from core.models import Agent, Media


class AgentSerializer(serializers.HyperlinkedModelSerializer):
    media = serializers.HyperlinkedIdentityField(
        view_name="media-detail",
        format="html",
        many=True,
    )

    class Meta:
        model = Agent
        fields = ["id", "created_at", "name", "media"]


class MediaSerializer(serializers.HyperlinkedModelSerializer):
    contributors = serializers.HyperlinkedIdentityField(
        view_name="agent-detail",
        many=True,
        format="html",
    )

    class Meta:
        model = Media
        fields = [
            "id",
            "created_at",
            "title",
            "contributors",
            "media_type",
            "status",
            "pub_year",
            "review",
            "score",
            "review_date",
        ]
