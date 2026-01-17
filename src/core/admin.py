from django.contrib import admin

from core.models import Agent, Media, SavedView, Tag

admin.site.register(Agent)
admin.site.register(Media)
admin.site.register(SavedView)
admin.site.register(Tag)
