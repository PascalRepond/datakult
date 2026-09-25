"""
Tests for core.import_results module.

These tests verify that the search results of every metadata source take the one shape of the import page.
"""

from urllib.parse import parse_qs, urlsplit

from django.template.loader import render_to_string
from django.urls import reverse

from core.import_results import (
    ImportResult,
    from_googlebooks,
    from_igdb,
    from_musicbrainz,
    from_openlibrary,
    from_tmdb,
)
from core.services.googlebooks import GoogleBooksResult
from core.services.igdb import IGDBResult
from core.services.musicbrainz import MusicBrainzResult
from core.services.openlibrary import OpenLibraryResult
from core.services.tmdb import TMDBResult


def _split(url):
    """Return the path of a URL and its query parameters."""
    parts = urlsplit(url)
    return parts.path, {key: values[0] for key, values in parse_qs(parts.query).items()}


def test_tmdb_result():
    """A TMDB result shows its original title when it differs, and imports with its type and language."""
    result = TMDBResult(
        tmdb_id=438631,
        title="Dune",
        original_title="Dune: Part One",
        year=2021,
        overview="Spice.",
        cover_path=None,
        media_type="movie",
    )

    shown = from_tmdb(result, media_id=None, lang="fr-FR")

    assert (shown.title, shown.year, shown.badge) == ("Dune", 2021, "Film")
    assert (shown.note, shown.description) == ("(Dune: Part One)", "Spice.")
    assert _split(shown.import_url) == (
        reverse("media_add"),
        {"tmdb_id": "438631", "media_type": "movie", "lang": "fr-FR"},
    )


def test_igdb_result():
    """An IGDB result shows the name and summary of its game."""
    result = IGDBResult(igdb_id=1, name="Hades", year=2020, summary="Escape.", cover_url=None, cover_url_small=None)

    shown = from_igdb(result, media_id=None)

    assert (shown.title, shown.description, shown.badge) == ("Hades", "Escape.", "Video game")
    assert _split(shown.import_url) == (reverse("media_add"), {"igdb_id": "1"})


def test_book_results():
    """Book results show their authors and source, and import from it."""
    google = GoogleBooksResult(volume_id="v1", title="Dune", authors=["Frank Herbert"], year=1965, thumbnail_url=None)
    library = OpenLibraryResult(
        work_key="/works/OL1W", title="Dune", authors=["Frank Herbert", "X"], year=1965, cover_id=None
    )

    shown_google = from_googlebooks(google, media_id=None)
    shown_library = from_openlibrary(library, media_id=None)

    assert (shown_google.byline, shown_google.badge) == ("Frank Herbert", "Google Books")
    assert (shown_library.byline, shown_library.badge) == ("Frank Herbert, X", "OpenLibrary")
    assert _split(shown_google.import_url) == (reverse("media_add"), {"googlebooks_id": "v1"})
    assert _split(shown_library.import_url) == (reverse("media_add"), {"openlibrary_key": "OL1W", "year": "1965"})


def test_musicbrainz_result():
    """A MusicBrainz result shows its artists, country and label, with a square cover."""
    result = MusicBrainzResult(
        mbid="m1", title="Abbey Road", artists=["The Beatles"], year=1969, country="GB", label="Apple"
    )

    shown = from_musicbrainz(result, media_id=None)

    assert (shown.byline, shown.note, shown.detail, shown.badge) == ("The Beatles", "GB", "Apple", "Album")
    assert shown.square_cover
    assert _split(shown.import_url) == (reverse("media_add"), {"musicbrainz_id": "m1"})


def test_results_of_a_media_being_edited_import_into_it():
    """When importing into an existing media, a result leads to its edit form."""
    result = IGDBResult(igdb_id=1, name="Hades", year=None, summary="", cover_url=None, cover_url_small=None)

    assert _split(from_igdb(result, media_id=7).import_url) == (reverse("media_edit", args=[7]), {"igdb_id": "1"})


def test_import_results_template_shows_every_result():
    """Every result is shown with its title and badge, linking to its import, with a placeholder for a missing cover."""
    results = [
        ImportResult(
            title="Dune", year=2021, badge="Film", import_url="/media/add/?tmdb_id=1", placeholder_icon="film"
        ),
        ImportResult(
            title="Hades",
            year=None,
            badge="Video game",
            import_url="/media/add/?igdb_id=2",
            placeholder_icon="gamepad-2",
        ),
    ]

    html = render_to_string("partials/import/import_results.html", {"results": results, "query": "d"})

    for result in results:
        assert result.title in html
        assert result.badge in html
        assert f'href="{result.import_url}"' in html
