from django.views.generic import ListView, DetailView
from itertools import chain

from .models import BookWork, Game, Movie, Series

class WorkListView(ListView):
  template_name = 'library/work_list.html'
  paginate_by = 25

  def get_context_data(self, **kwargs):
    context = super(WorkListView, self).get_context_data(**kwargs)
    return context
  
  def get_queryset(self):
    books = BookWork.objects.all()
    games = Game.objects.all()
    movies = Movie.objects.all()
    series = Series.objects.all()

    # combine
    queryset_chain = chain(books, games, movies, series)
    qs = sorted(queryset_chain,
    key = lambda instance: instance.pk,
    reverse=True)
    self.count = len(qs)
    return qs