from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("media/<int:pk>/edit/", views.media_edit, name="media_edit"),
    path("agents/<int:pk>/", views.agent, name="agent_detail"),
    path("search/", views.search_media, name="search"),
]
