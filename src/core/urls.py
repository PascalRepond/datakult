from django.urls import path

from .views import backup, home, imports, lists, media, saved_views, stats

urlpatterns = [
    path("", home.home, name="home"),
    path("media/", media.index, name="media_list"),
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
    # Lists
    path("lists/", lists.list_index, name="list_index"),
    path("lists/load-more/", lists.load_more_lists, name="load_more_lists"),
    path("lists/add/", lists.list_edit, name="list_add"),
    path("lists/<int:pk>/", lists.list_detail, name="list_detail"),
    path("lists/<int:pk>/edit/", lists.list_edit, name="list_edit"),
    path("lists/<int:pk>/delete/", lists.list_delete, name="list_delete"),
    path("lists/<int:pk>/search/", lists.list_media_search, name="list_media_search"),
    path("lists/<int:pk>/add-media/", lists.list_entry_add, name="list_entry_add"),
    path("list-entries/<int:pk>/remove/", lists.list_entry_remove, name="list_entry_remove"),
    path("list-entries/<int:pk>/move/", lists.list_entry_move, name="list_entry_move"),
    path("media/<int:pk>/lists/", lists.media_lists_htmx, name="media_lists_htmx"),
    path("media/<int:pk>/lists/search/", lists.media_lists_search_htmx, name="media_lists_search_htmx"),
]
