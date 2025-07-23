from django.http import HttpResponse


def index(request):
    return HttpResponse("Hello, world. You're at the media index.")


def media_detail(request, media_id):
    return HttpResponse()
