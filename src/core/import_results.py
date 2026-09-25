"""Search results of every metadata source, in the one shape shown by the import page."""

from dataclasses import dataclass

from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext as _


@dataclass
class ImportResult:
    """A search result of any metadata source, as the import page shows it."""

    title: str
    year: int | None
    badge: str  # The kind of media or the source
    import_url: str  # The media form, filled with the metadata of the result
    placeholder_icon: str  # Shown without cover
    cover_url: str | None = None
    note: str = ""  # Shown after the year, such as an original title or a country
    byline: str = ""  # Authors or artists
    description: str = ""
    detail: str = ""  # Shown last and smaller, such as a record label
    square_cover: bool = False


def _import_url(media_id, **params):
    """Return the form of a new media, or of the media being imported into, with the parameters of a result."""
    url = reverse("media_edit", args=[media_id]) if media_id else reverse("media_add")
    return f"{url}?{urlencode({key: value for key, value in params.items() if value})}"


def from_tmdb(result, media_id, lang):
    """Return a TMDB result, as the import page shows it."""
    return ImportResult(
        title=result.title,
        year=result.year,
        badge=_("Film") if result.media_type == "movie" else _("TV"),
        import_url=_import_url(media_id, tmdb_id=result.tmdb_id, media_type=result.media_type, lang=lang),
        placeholder_icon="image-off",
        cover_url=result.cover_url_small,
        note=f"({result.original_title})" if result.original_title and result.original_title != result.title else "",
        description=result.overview,
    )


def from_igdb(result, media_id):
    """Return an IGDB result, as the import page shows it."""
    return ImportResult(
        title=result.name,
        year=result.year,
        badge=_("Video game"),
        import_url=_import_url(media_id, igdb_id=result.igdb_id),
        placeholder_icon="gamepad-2",
        cover_url=result.cover_url_small,
        description=result.summary,
    )


def from_googlebooks(result, media_id):
    """Return a Google Books result, as the import page shows it."""
    return ImportResult(
        title=result.title,
        year=result.year,
        badge="Google Books",
        import_url=_import_url(media_id, googlebooks_id=result.volume_id),
        placeholder_icon="book",
        cover_url=result.cover_url_small,
        byline=", ".join(result.authors),
    )


def from_openlibrary(result, media_id):
    """Return an OpenLibrary result, as the import page shows it."""
    return ImportResult(
        title=result.title,
        year=result.year,
        badge="OpenLibrary",
        import_url=_import_url(media_id, openlibrary_key=result.olid, year=result.year),
        placeholder_icon="book",
        cover_url=result.cover_url_small,
        byline=", ".join(result.authors),
    )


def from_musicbrainz(result, media_id):
    """Return a MusicBrainz result, as the import page shows it."""
    return ImportResult(
        title=result.title,
        year=result.year,
        badge=_("Album"),
        import_url=_import_url(media_id, musicbrainz_id=result.mbid),
        placeholder_icon="disc-3",
        cover_url=result.cover_url_small,
        note=result.country or "",
        byline=", ".join(result.artists),
        detail=result.label or "",
        square_cover=True,
    )
