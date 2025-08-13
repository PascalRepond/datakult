from django.urls import path

from . import views

urlpatterns = [
    path("home/", views.index, name="home"),
    path("", views.media, name="media_list"),
    path("agents/<int:pk>/", views.agent, name="agent_detail"),
    path("media/<int:pk>/", views.media_detail, name="media_detail"),
    path("search/", views.search_media, name="search"),
]
