from django.urls import path

from . import views
from .htmx_validation import validate_media_field

urlpatterns = [
    path("", views.index, name="home"),
    path("media/add/", views.media_edit, name="media_add"),
    path("media/<int:pk>/edit/", views.media_edit, name="media_edit"),
    path("media/<int:pk>/delete/", views.media_delete, name="media_delete"),
    path("search/", views.search_media, name="search"),
    path("load-more/", views.load_more_media, name="load_more_media"),
    path("agents/search-htmx/", views.agent_search_htmx, name="agent_search_htmx"),
    path("agents/select-htmx/", views.agent_select_htmx, name="agent_select_htmx"),
    path("media/validate_field/", validate_media_field, name="media_validate_field"),
    path("media/<int:pk>/review-full/", views.media_review_full_htmx, name="media_review_full_htmx"),
    path("media/<int:pk>/review-clamped/", views.media_review_clamped_htmx, name="media_review_clamped_htmx"),
    # Backup management
    path("backup/", views.backup_manage, name="backup_manage"),
    path("backup/export/", views.backup_export, name="backup_export"),
    path("backup/import/", views.backup_import, name="backup_import"),
]
