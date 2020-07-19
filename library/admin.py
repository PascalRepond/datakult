from django.contrib import admin
from .models import Person, Collectivity, BookWork, BookEdition, Platform, GameSeries, Game, Movie, MovieSeries, Series

admin.site.register(Person)
admin.site.register(Collectivity)
admin.site.register(BookWork)
admin.site.register(BookEdition)
admin.site.register(Platform)
admin.site.register(GameSeries)
admin.site.register(Game)
admin.site.register(Movie)
admin.site.register(MovieSeries)
admin.site.register(Series)