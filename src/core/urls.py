from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("media/add/", views.media_edit, name="media_add"),
    path("media/<int:pk>/edit/", views.media_edit, name="media_edit"),
    path("media/<int:pk>/delete/", views.media_delete, name="media_delete"),
    path("agents/<int:pk>/", views.agent, name="agent_detail"),
    path("search/", views.search_media, name="search"),
    path("agents/search-htmx/", views.agent_search_htmx, name="agent_search_htmx"),
    path("agents/select-htmx/", views.agent_select_htmx, name="agent_select_htmx"),
]
