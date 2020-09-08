from django.db import models
from isbn_field import ISBNField
from django.utils.translation import gettext as _
from djrichtextfield.models import RichTextField

DATE_PRECISION = (
    ('1', _('Year')),
    ('2', _('Month')),
    ('3', _('Day')),
    )

class Agent(models.Model):
    """ An agent is an entity responsible for a work (it can be either a person or a collectivity) """
    wikidata_uri = models.CharField(
        # Wikidata URI can be used to retrieve additionnal info 
        # about the agent using the Wikidata API
        _('Wikidata URI'), 
        max_length=64, blank=True, null=True, unique=True, 
        help_text=_("Example: Q310155")
        )

    class Meta:
        abstract = True
        verbose_name = _("agent")
        verbose_name_plural = _("agents")


class Person(Agent):
    name = models.CharField(_('Name'),
    max_length=124, db_index=True, default="name",
    help_text=_("Name or (artist name/pen name) under which the person is most well-known.")
    )
    birth_date = models.DateField(_('Date of birth'), blank=True, null=True)
    death_date = models.DateField(_('Date of death'), blank=True, null=True)
    image = models.ImageField(
        upload_to='persons/', blank=True, null=True)
    biography = RichTextField(_('Biography'), blank=True, null=True)

    def __str__(self):
        return self.name


class Collectivity(Agent):
    """ Company, group, corporation, etc. """
    name = models.CharField(_('Name'), max_length=124, null=True, db_index=True)
    logo = models.ImageField(
        upload_to='collectivities/', blank=True, null=True)
    summary = RichTextField(_('Summary'), blank=True, null=True)

    class Meta:
        verbose_name = _('collectivity')
        verbose_name_plural = _('collectivities')

    def __str__(self):
        return self.name


# The Work meta-model provides the basic fields and methods that are shared by 
# all other models be they books, movies, games, you name it.

# !! This model does not represent Bibframe's or RDA's "work" entity level !!

class Work(models.Model):
    """
    The Work meta-model provides the basic fields and methods that are shared by 
    all other models be they books, movies, games, you name it.

    !! This model does not represent Bibframe's or RDA's "work" entity level !!
    """
    title = models.CharField(
        _('Original title'), max_length=255, 
        help_text=_("Provide the title in its original language.")
        )
    date = models.DateField(
        _('First publication date'), blank=True, null=True, 
        help_text=_("If specific date is unknown, enter January 1st")
        )
    date_precision = models.IntegerField(
        _('Date precision'),
        default=3,
        choices=DATE_PRECISION
        )
    cover = models.ImageField(upload_to='covers/', blank=True, null=True)
    summary = RichTextField(_('Summary'), blank=True, null=True)
    wikidata_uri = models.CharField(
        # Wikidata URI can be used to retrieve additionnal info 
        # about the work using the Wikidata API
        _('Wikidata URI'),
        max_length=64, blank=True, null=True, unique=True, 
        help_text=_("Example: Q3107329")
        )

    class Meta:
        abstract = True

    def __str__(self):
        return self.title

# BOOKS 📚

class BookSeries(Work):
    author = models.ManyToManyField(
        Person, blank=True, verbose_name=_('Author'), related_name='bookseries_of_author')

    class Meta:
        verbose_name = _("book series")
        verbose_name_plural = _("book series")

    def __str__(self):
        return self.title


class BookWork(Work):
    BOOK_TYPES = (
        ('BK', _('Book')),
        ('BD', _('Comic/Graphic novel')),
        ('MA', _('Manga')),
    )

    author = models.ManyToManyField(
        Person, blank=True, verbose_name=_('Author'), related_name='bookworks_of_author')
    illustrator = models.ManyToManyField(
        Person, verbose_name=_('Illustrator'), related_name='bookworks_of_illustrator', blank=True)
    book_type = models.CharField(_('Book type'), max_length=2, choices=BOOK_TYPES)
    origin_lang = models.CharField(
        _('Original language'), max_length=2, blank=True, null=True)
    series = models.ForeignKey(
        BookSeries,
        on_delete=models.PROTECT,
        verbose_name=_('Book series'),
        null=True,
        blank=True,
        related_name='bookworks_of_series')
    series_vol = models.IntegerField(_('Volume in the series'), blank=True, null=True)
    summary = RichTextField(_('Summary'), blank=True, null=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return "/books/%i/" % self.id


class BookEdition(Work):

    book_work = models.ForeignKey(
        BookWork, on_delete=models.PROTECT, 
        verbose_name=_('Book work'), related_name='editions_of_bookwork',
        help_text=_("Which book work is this an edition of?"))
    title = models.CharField(_('Edition title'), max_length=255, help_text=_("Title of this specific edition"))
    date = models.DateField(_('Edition date'), blank=True)
    translator = models.ManyToManyField(
        Person, verbose_name=_('Translator'), blank=True)
    ed_lang = models.CharField(_('Edition language'), max_length=2)
    publisher = models.ForeignKey(
        Collectivity, on_delete=models.SET_NULL, blank=True, null=True, 
        verbose_name=_('Publisher'), related_name='bookeditions_of_publisher')
    pages = models.PositiveIntegerField(_('Number of pages'))
    isbn = ISBNField('ISBN', blank=True, null=True)

    def __str__(self):
        return self.title


# GAMES

class Platform(models.Model):
    ''' Gaming platform '''
    wikidata_uri = models.CharField(
        # Wikidata URI can be used to retrieve additionnal info 
        # about the work using the Wikidata API
        _('Wikidata URI'),
        max_length=64, blank=True, null=True, unique=True, 
        help_text=_("Example: Q5014725")
        )
    igdb_id = models.CharField(
        _('IGDB ID'),
        max_length=64, blank=True, null=True, unique=True,
        help_text=_("Example: ps4--1"))

    logo = models.ImageField(
        upload_to='logos/platforms/', blank=True, null=True)
    name = models.CharField(_('Name'), max_length=50)
    description = models.TextField(_('Description'))
    date = models.DateField(_('Publication date'))
    date_precision = models.IntegerField(
        _('Date precision'),
        default=3,
        choices=DATE_PRECISION
        )
    website = models.URLField(_('Official website'), blank=True, null=True)

    def __str__(self):
        return self.name


class GameSeries(Work):

    class Meta:
        verbose_name = _("game series")
        verbose_name_plural = _("game series")

    def __str__(self):
        return self.title


class Game(Work):

    igdb_id = models.CharField(
        _('IGDB ID'),
        max_length=64, blank=True, null=True, unique=True,
        help_text=_("Example: assassin-s-creed"))

    # title, date, cover, viaf, wikidata
    dev = models.ManyToManyField(
        Collectivity,
        blank=True,
        related_name='games_of_dev',
        verbose_name=_('Developer')
    )
    publisher = models.ManyToManyField(
        Collectivity,
        blank=True,
        related_name='games_of_publisher',
        verbose_name=_('Publisher')
    )
    platform = models.ManyToManyField(
        Platform,
        blank=True,
        related_name='games_of_platform',
        verbose_name=_('Platform'),
        help_text=_("Platform on which the game is or has been available")
    )
    series = models.ForeignKey(
        GameSeries,
        on_delete=models.PROTECT,
        verbose_name=_('Game series'),
        null=True,
        blank=True,
        related_name='game_of_series')
    series_no = models.IntegerField(_('Number in series'), blank=True, null=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return "/games/%i/" % self.id


# MOVIES

class MovieSeries(Work):
    tmdb_id = models.CharField(_('TMDB ID'), max_length=24, blank=True, null=True)

    def __str__(self):
        return self.title


class Movie(Work):

    # META : title, date, cover, viaf, wikidata
    director = models.ManyToManyField(
        Person,
        blank=True,
        verbose_name=_('Director'),
        related_name='movies_of_director',
    )
    executive_producer = models.ManyToManyField(
        Person,
        blank=True,
        verbose_name=_('Executive producer'),
        related_name='movies_of_producer',
    )
    cast = models.ManyToManyField(
        Person,
        blank=True,
        verbose_name=_('Cast'),
        related_name='movies_of_actor',
    )
    series = models.ForeignKey(
        MovieSeries,
        on_delete=models.PROTECT,
        verbose_name=_('Series'),
        null=True,
        blank=True,
        related_name='movies_of_series'
    )
    series_no = models.IntegerField(_('Number in series'), blank=True, null=True)
    
    origin_lang = models.CharField(
        _('Original language'), max_length=2, blank=True, null=True)

    tmdb_id = models.CharField(
        _('TMDB ID'), 
        max_length=24, blank=True, null=True,
        help_text=_('Example: 122')
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return "/movies/%i/" % self.id


# SERIES

class Series(Work):
    # title, date, cover, viaf, wikidata
    executive_producer = models.ManyToManyField(
        Person,
        blank=True,
        verbose_name=_('Executive producer'),
        related_name='series_of_producer'
    )
    production_company = models.ManyToManyField(
        Collectivity,
        blank=True,
        verbose_name=_('Producting company'),
        related_name='series_of_company'
    )
    actor = models.ManyToManyField(
        Person,
        blank=True,
        verbose_name=_('Cast'),
        related_name='series_of_actor'
    )
    origin_lang = models.CharField(
        _('Original language'), max_length=2, blank=True, null=True)

    tmdb_id = models.CharField(
        _('TMDB ID'), 
        max_length=24, blank=True, null=True,
        help_text=_('Example: 122')
    )

    class Meta:
        verbose_name = _("series")
        verbose_name_plural = _("series")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return "/series/%i/" % self.id