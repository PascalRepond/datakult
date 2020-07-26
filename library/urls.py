from django.urls import path

from .views import WorkListView, BookDetailView, GameDetailView, MovieDetailView, SeriesDetailView

urlpatterns = [
  path('lib/', WorkListView.as_view(), name='work_list'),
  # BOOKS
  path('books/<int:pk>/', BookDetailView.as_view(), name='bookwork_detail'),
  # GAMES
  path('games/<int:pk>/', GameDetailView.as_view(), name='game_detail'),
  # MOVIES
  path('movies/<int:pk>/', MovieDetailView.as_view(), name='movie_detail'),
  # SERIES
  path('series/<int:pk>/', SeriesDetailView.as_view(), name='series_detail'),
]