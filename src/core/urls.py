from django.urls import path

from .views import backup, imports, media, saved_views, stats

urlpatterns = [
    path("", media.index, name="home"),
    path("media/add/", media.media_edit, name="media_add"),
    path("media/import/", imports.media_import, name="media_import"),
    path("media/<int:pk>/", media.media_detail, name="media_detail"),
    path("stats/", stats.stats, name="stats"),
    path("stats/covers/", stats.stats_covers_htmx, name="stats_covers_htmx"),
    path("media/<int:pk>/edit/", media.media_edit, name="media_edit"),
    path("media/<int:pk>/delete/", media.media_delete, name="media_delete"),
    path("load-more/", media.load_more_media, name="load_more_media"),
    path("agents/search-htmx/", media.agent_search_htmx, name="agent_search_htmx"),
    path("agents/select-htmx/", media.agent_select_htmx, name="agent_select_htmx"),
    path("tags/search-htmx/", media.tag_search_htmx, name="tag_search_htmx"),
    path("tags/select-htmx/", media.tag_select_htmx, name="tag_select_htmx"),
    path("import-search/", imports.import_search_htmx, name="import_search_htmx"),
    path("media/validate_field/", media.validate_media_field, name="media_validate_field"),
    path("media/<int:pk>/review/", media.media_review_htmx, name="media_review_htmx"),
    # Backup management
    path("backup/", backup.backup_manage, name="backup_manage"),
    path("backup/export/", backup.backup_export, name="backup_export"),
    path("backup/import/", backup.backup_import, name="backup_import"),
    # Saved views
    path("saved-views/save/", saved_views.saved_view_save, name="saved_view_save"),
    path("saved-views/<int:pk>/delete/", saved_views.saved_view_delete, name="saved_view_delete"),
]
