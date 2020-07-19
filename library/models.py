from django.db import models
from isbn_field import ISBNField

# An agent is an entity responsible for a work (it can be either a person or a collectivity)

class Agent(models.Model):
    viaf_id = models.CharField('VIAF ID', blank=True, null=True, max_length=64)
    wikidata_uri = models.CharField(
        'Wikidata URI', max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class Person(Agent):
    last_name = models.CharField('Last name', max_length=124)
    first_name = models.CharField('First name', max_length=124)
    birth_date = models.DateField('Date of birth', blank=True, null=True)
    death_date = models.DateField('Date of death', blank=True, null=True)
    image = models.ImageField(
        upload_to='persons/', blank=True, null=True)

    def __str__(self):
        return self.first_name+" "+self.last_name


class Collectivity(Agent):
    name = models.CharField('Name', max_length=124, blank=True, null=True)
    logo = models.ImageField(
        upload_to='collectivities/', blank=True, null=True)

    def __str__(self):
        return self.name


# The Work meta-model provides the basic fields and methods that are shared by 
# all other models be they books, movies, games, you name it.

# !! This model does not represent Bibframe's or RDA's "work" entity level !!

class Work(models.Model):

    title = models.CharField('Original title', max_length=255)
    date = models.DateField('First publication date', blank=True, null=True)
    cover = models.ImageField(upload_to='covers/', blank=True, null=True)
    viaf_id = models.CharField('VIAF ID', blank=True, null=True, max_length=64)
    wikidata_uri = models.CharField(
        'Wikidata URI', max_length=64, blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

# BOOKS 📚


class BookSeries(Work):
    author = models.ManyToManyField(
        Person, blank=True, verbose_name='Author', related_name='bookseries_of_author')

    def __str__(self):
        return self.title


class BookWork(Work):
    BOOK_TYPES = (
        ('BK', 'Book'),
        ('BD', 'BD/Comic/GN'),
        ('MA', 'Manga'),
    )

    author = models.ManyToManyField(
        Person, blank=True, verbose_name='Author', related_name='bookworks_of_author')
    illustrator = models.ManyToManyField(
        Person, verbose_name='Illustrator', related_name='bookworks_of_illustrator', blank=True)
    book_type = models.CharField('Book type', max_length=2, choices=BOOK_TYPES)
    origin_lang = models.CharField(
        'Original language', max_length=2, blank=True, null=True)
    series = models.ForeignKey(
        BookSeries,
        on_delete=models.PROTECT,
        verbose_name='Series',
        null=True,
        blank=True,
        related_name='bookworks_of_series')
    series_vol = models.IntegerField('Volume', blank=True, null=True)
    summary = models.TextField('Summary', blank=True, null=True)

    def __str__(self):
        return self.title


class BookEdition(Work):

    book_work = models.ForeignKey(
        BookWork, on_delete=models.PROTECT, related_name='editions_of_bookwork')
    title = models.CharField('Edition title', max_length=255)
    date = models.DateField('Edition date', blank=True)
    translator = models.ManyToManyField(
        Person, verbose_name='Translator', blank=True)
    ed_lang = models.CharField('Edition language', max_length=2)
    publisher = models.ForeignKey(
        Collectivity, on_delete=models.SET_NULL, blank=True, null=True, related_name='bookeditions_of_publisher')
    pages = models.PositiveIntegerField('Nb. of pages')
    isbn = ISBNField('ISBN', blank=True, null=True)

    def __str__(self):
        return self.title


# GAMES

class Platform(models.Model):
    id = models.CharField('Id', max_length=24, unique=True, primary_key=True)
    logo = models.ImageField(
        upload_to='logos/platforms/', blank=True, null=True)
    name = models.CharField('Name', max_length=50)
    description = models.TextField('Description')
    date = models.DateField('Publication date')
    website = models.URLField('Official website', blank=True, null=True)
    wikidata_uri = models.CharField('Wikidata URI', max_length=64, blank=True, null=True)
    igdb_id = models.CharField('IGDB ID', max_length=64, blank=True, null=True)

    def __str__(self):
        return self.name


class GameSeries(Work):
    igdb_id = models.CharField('IGDB ID', max_length=64, blank=True, null=True)

    def __str__(self):
        return self.title


class Game(Work):

    # title, date, cover, viaf, wikidata
    dev = models.ManyToManyField(
        Collectivity,
        blank=True,
        related_name='games_of_dev'
    )
    publisher = models.ManyToManyField(
        Collectivity,
        blank=True,
        related_name='games_of_publisher'
    )
    platform = models.ManyToManyField(
        Platform,
        blank=True,
        related_name='games_of_platform'
    )
    series = models.ForeignKey(
        GameSeries,
        on_delete=models.PROTECT,
        verbose_name='Series',
        null=True,
        blank=True,
        related_name='bookworks_of_series')
    series_no = models.IntegerField('Number in series', blank=True, null=True)
    igdb_id = models.CharField('IGDB ID', max_length=64, blank=True, null=True)

    def __str__(self):
        return self.title


# MOVIES

class MovieSeries(Work):
    tmdb_id = models.CharField('TMDB ID', max_length=24, blank=True, null=True)

    def __str__(self):
        return self.title


class Movie(Work):

    # title, date, cover, viaf, wikidata
    director = models.ManyToManyField(
        Person,
        blank=True,
        related_name='movies_of_director'
    )
    executive_producer = models.ManyToManyField(
        Person,
        blank=True,
        related_name='movies_of_producer'
    )
    actor = models.ManyToManyField(
        Person,
        blank=True,
        related_name='movies_of_actor'
    )
    series = models.ForeignKey(
        MovieSeries,
        on_delete=models.PROTECT,
        verbose_name='Series',
        null=True,
        blank=True,
        related_name='bookworks_of_series')
    origin_lang = models.CharField(
        'Original language', max_length=2, blank=True, null=True)
    series_no = models.IntegerField('Number in series', blank=True, null=True)
    tmdb_id = models.CharField('TMDB ID', max_length=24, blank=True, null=True)

    def __str__(self):
        return self.title


# SERIES

class Series(Work):
    # title, date, cover, viaf, wikidata
    executive_producer = models.ManyToManyField(
        Person,
        blank=True,
        related_name='series_of_producer'
    )
    production_company = models.ManyToManyField(
        Collectivity,
        blank=True,
        related_name='series_of_company'
    )
    actor = models.ManyToManyField(
        Person,
        blank=True,
        related_name='series_of_actor'
    )
    origin_lang = models.CharField(
        'Original language', max_length=2, blank=True, null=True)
    tmdb_id = models.CharField('TMDB ID', max_length=24, blank=True, null=True)