"""Helpers shared by the test modules."""

from io import BytesIO

from django.contrib.messages import get_messages
from PIL import Image


def media_form_data(**overrides):
    """Return the POST data of a valid media form, which matches the `media` fixture, with some fields overridden."""
    return {"title": "Test Media", "media_type": "BOOK", "status": "PLANNED", **overrides}


def image_bytes(size=(100, 100), color="#333333", fmt="PNG", mode="RGB"):
    """Return the bytes of an image of a single colour."""
    output = BytesIO()
    Image.new(mode, size, color=color).save(output, format=fmt)
    return output.getvalue()


def titles(response):
    """Return the titles of the media listed by a response, in their order."""
    return [media.title for media in response.context["media_list"]]


def messages_of(response):
    """Return the texts of the messages that a request queued."""
    return [str(message) for message in get_messages(response.wsgi_request)]
