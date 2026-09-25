"""
Tests for core.views.imports: the searches of the metadata sources, and the import of their metadata.
"""

import logging
import re
from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse
from django.urls import reverse

from core.services.base import APIError
from core.services.googlebooks import GoogleBooksResult
from core.services.musicbrainz import MusicBrainzResult
from core.services.openlibrary import OpenLibraryResult
from core.views.imports import IMPORT_SEARCHES


def test_import_page_title_depends_on_its_purpose(logged_in_client, media):
    """The import page is titled as adding a media, or as importing metadata into an existing one."""
    adding = logged_in_client.get(reverse("media_import")).content.decode()
    importing = logged_in_client.get(reverse("media_import"), {"media_id": media.pk}).content.decode()

    assert "Add media</h1>" in adding
    assert "Import metadata</h1>" in importing


def test_import_page_has_one_search_for_every_source(logged_in_client, media_factory):
    """The import page has a single search field, and picks the source of the media type."""
    media = media_factory(media_type="GAME", title="Hades")

    content = logged_in_client.get(
        reverse("media_import"), {"media_id": media.pk, "media_type": "GAME", "title": "Hades"}
    ).content.decode()

    assert content.count('name="q"') == 1
    assert re.search(r'name="q"[^>]*value="Hades"', content)
    assert content.count('name="source"') == 4
    assert re.search(r'name="source"\s+value="igdb"[^>]*\schecked', content)


@pytest.mark.parametrize("source", ["tmdb", "igdb", "books", "musicbrainz"])
def test_import_search_uses_the_picked_source(logged_in_client, monkeypatch, source):
    """The single search of the import page searches the source picked in its tabs."""
    monkeypatch.setitem(IMPORT_SEARCHES, source, lambda _request: HttpResponse(f"searched {source}"))

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": "dune"})

    assert response.content.decode() == f"searched {source}"


@pytest.mark.parametrize("params", [{"q": "dune"}, {"source": "unknown", "q": "dune"}])
def test_import_search_rejects_an_unknown_source(logged_in_client, params):
    """A search without a known source is a bad request."""
    assert logged_in_client.get(reverse("import_search_htmx"), params).status_code == 400


@pytest.mark.parametrize("query", ["", "a"])
@pytest.mark.parametrize("source", ["tmdb", "igdb", "books", "musicbrainz"])
def test_import_search_waits_for_a_longer_query(logged_in_client, source, query):
    """A query shorter than two characters searches nothing, whatever the source, and keeps the edited media."""
    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": query, "media_id": "42"})

    assert "partials/import/import_results.html" in [t.name for t in response.templates]
    assert response.context["results"] == []
    assert response.context["media_id"] == "42"


IMPORTS = {
    "tmdb movie": (
        {"tmdb_id": "438631", "media_type": "movie", "lang": "fr-FR"},
        {
            "https://api.themoviedb.org/3/movie/438631": {
                "title": "Dune",
                "original_title": "Dune",
                "release_date": "2021-09-15",
                "credits": {
                    "crew": [{"name": "Denis Villeneuve", "job": "Director"}, {"name": "Eric", "job": "Writer"}]
                },
                "production_companies": [{"name": "Legendary"}, {"name": "Warner"}, {"name": "Villeneuve Films"}],
                "genres": [{"name": "Science Fiction"}],
                "poster_path": "/dune.jpg",
            }
        },
        {
            "initial": {
                "title": "Dune",
                "pub_year": 2021,
                "media_type": "FILM",
                "external_uri": "https://www.themoviedb.org/movie/438631",
            },
            "import_contributors": ["Denis Villeneuve", "Legendary", "Warner"],
            "import_tags": ["Science Fiction"],
            "cover_url": "https://image.tmdb.org/t/p/w500/dune.jpg",
        },
    ),
    "tmdb tv": (
        {"tmdb_id": "95396", "media_type": "tv"},
        {
            "https://api.themoviedb.org/3/tv/95396": {
                "name": "Severance",
                "first_air_date": "2022-02-18",
                "created_by": [{"name": "Dan Erickson"}],
                "genres": [{"name": "Drama"}],
            }
        },
        {
            "initial": {
                "title": "Severance",
                "pub_year": 2022,
                "media_type": "TV",
                "external_uri": "https://www.themoviedb.org/tv/95396",
            },
            "import_contributors": ["Dan Erickson"],
            "import_tags": ["Drama"],
            "cover_url": None,
        },
    ),
    "igdb": (
        {"igdb_id": "1"},
        {
            "https://id.twitch.tv/oauth2/token": {"access_token": "token", "expires_in": 3600},
            "https://api.igdb.com/v4/games": [
                {
                    "name": "Hades",
                    "first_release_date": 1600387200,
                    "url": "https://www.igdb.com/games/hades",
                    "cover": {"image_id": "co1"},
                    "involved_companies": [
                        {"company": {"name": "Supergiant"}, "developer": True, "publisher": True},
                        {"company": {"name": "Publisher"}, "developer": False, "publisher": True},
                    ],
                    "genres": [{"name": "Roguelike"}],
                }
            ],
        },
        {
            "initial": {
                "title": "Hades",
                "pub_year": 2020,
                "media_type": "GAME",
                "external_uri": "https://www.igdb.com/games/hades",
            },
            "import_contributors": ["Supergiant"],
            "import_tags": ["Roguelike"],
            "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co1.jpg",
        },
    ),
    "google books": (
        {"googlebooks_id": "vol1"},
        {
            "https://www.googleapis.com/books/v1/volumes/vol1": {
                "volumeInfo": {
                    "title": "Dune",
                    "subtitle": "Deluxe Edition",
                    "authors": ["Frank Herbert"],
                    "publishedDate": "1965-08",
                    "categories": ["Fiction"],
                    "imageLinks": {"thumbnail": "http://books.google.com/books/content?id=vol1&zoom=1"},
                    "canonicalVolumeLink": "https://books.google.com/books/about/Dune.html",
                }
            }
        },
        {
            "initial": {
                "title": "Dune: Deluxe Edition",
                "pub_year": 1965,
                "media_type": "BOOK",
                "external_uri": "https://books.google.com/books/about/Dune.html",
            },
            "import_contributors": ["Frank Herbert"],
            "import_tags": ["Fiction"],
            "cover_url": "https://books.google.com/books/content?id=vol1&fife=w800-h1200",
        },
    ),
    "openlibrary": (
        {"openlibrary_key": "OL1W", "year": "1965"},
        {
            "https://openlibrary.org/works/OL1W.json": {
                "title": "Dune",
                "covers": [42],
                "authors": [{"author": {"key": "/authors/OL2A"}}],
            },
            "https://openlibrary.org/authors/OL2A.json": {"name": "Frank Herbert"},
        },
        {
            "initial": {
                "title": "Dune",
                "pub_year": 1965,
                "media_type": "BOOK",
                "external_uri": "https://openlibrary.org/works/OL1W",
            },
            "import_contributors": ["Frank Herbert"],
            "import_tags": [],
            "cover_url": "https://covers.openlibrary.org/b/id/42-L.jpg",
        },
    ),
    "musicbrainz": (
        {"musicbrainz_id": "abc-123"},
        {
            "https://musicbrainz.org/ws/2/release/abc-123": {
                "title": "Abbey Road",
                "date": "1969-09-26",
                "artist-credit": [{"name": "The Beatles"}],
                "genres": [{"name": "rock"}],
                "tags": [{"name": "rock"}, {"name": "pop"}],
            }
        },
        {
            "initial": {
                "title": "Abbey Road",
                "pub_year": 1969,
                "media_type": "MUSIC",
                "external_uri": "https://musicbrainz.org/release/abc-123",
            },
            "import_contributors": ["The Beatles"],
            "import_tags": ["rock", "pop"],
            "cover_url": "https://coverartarchive.org/release/abc-123/front-500",
        },
    ),
}


@pytest.mark.parametrize(("params", "responses", "expected"), IMPORTS.values(), ids=IMPORTS.keys())
def test_import_fills_the_form_with_the_metadata_of_the_source(
    logged_in_client, api_responses, params, responses, expected
):
    """Importing from a source fills the form, and suggests its contributors, tags and cover."""
    api_responses.update(responses)

    response = logged_in_client.get(reverse("media_add"), params)

    assert response.context["form"].initial == expected["initial"]
    assert response.context["import_contributors"] == expected["import_contributors"]
    assert response.context["import_tags"] == expected["import_tags"]
    assert response.context["import_data"]["cover_url"] == expected["cover_url"]


def test_import_into_a_media_keeps_its_review_and_contributors(logged_in_client, api_responses, media):
    """Importing into a media keeps what was reviewed, and only suggests the contributors it does not have yet."""
    params, responses, _expected = IMPORTS["tmdb tv"]
    api_responses.update(responses)
    api_responses["https://api.themoviedb.org/3/tv/95396"]["created_by"].append({"name": "test author"})
    media.status, media.score, media.review = "COMPLETED", 8, "Unsettling."
    media.save()

    response = logged_in_client.get(reverse("media_edit", args=[media.pk]), params)

    initial = response.context["form"].initial
    assert (initial["title"], initial["status"], initial["score"], initial["review"]) == (
        "Severance",
        "COMPLETED",
        8,
        "Unsettling.",
    )
    assert response.context["import_contributors"] == ["Dan Erickson"]


def test_import_that_fails_shows_an_empty_form(logged_in_client, api_responses):
    """When the source cannot be reached, the form is shown empty rather than failing."""
    response = logged_in_client.get(reverse("media_add"), {"musicbrainz_id": "unknown"})

    assert response.context["import_data"] is None
    assert not response.context["form"].initial


SEARCHES = {
    "tmdb": {
        "https://api.themoviedb.org/3/search/multi": {
            "results": [
                {
                    "media_type": "movie",
                    "id": 1,
                    "title": "Dune",
                    "original_title": "Dune",
                    "release_date": "2021-09-15",
                },
                {"media_type": "tv", "id": 2, "name": "Dune: Prophecy", "first_air_date": "2024-11-17"},
                {"media_type": "person", "id": 3, "name": "Frank Herbert"},
            ]
        }
    },
    "igdb": {
        "https://id.twitch.tv/oauth2/token": {"access_token": "token", "expires_in": 3600},
        "https://api.igdb.com/v4/games": [{"id": 1, "name": "Dune: Spice Wars", "first_release_date": 1650931200}],
    },
    "books": {
        "https://openlibrary.org/search.json": {
            "docs": [
                {"key": "/works/OL1W", "title": "Dune", "author_name": "Frank Herbert", "first_publish_year": 1965}
            ]
        },
        "https://www.googleapis.com/books/v1/volumes": {
            "items": [
                {
                    "id": "v1",
                    "volumeInfo": {"title": "Dune Messiah", "authors": ["Frank Herbert"], "publishedDate": "1969"},
                }
            ]
        },
    },
    "musicbrainz": {
        "https://musicbrainz.org/ws/2/release": {
            "releases": [
                {"id": "m1", "title": "Dune (OST)", "date": "2021-09-03", "artist-credit": [{"name": "Hans Zimmer"}]}
            ]
        }
    },
}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("tmdb", [("Dune", 2021, ""), ("Dune: Prophecy", 2024, "")]),
        ("igdb", [("Dune: Spice Wars", 2022, "")]),
        ("books", [("Dune Messiah", 1969, "Frank Herbert"), ("Dune", 1965, "Frank Herbert")]),
        ("musicbrainz", [("Dune (OST)", 2021, "Hans Zimmer")]),
    ],
)
def test_import_search_shows_the_results_of_the_source(logged_in_client, api_responses, source, expected):
    """A search shows the works found by the source, with their year and authors, leaving out anything else."""
    api_responses.update(SEARCHES[source])

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": "dune"})

    assert [(result.title, result.year, result.byline) for result in response.context["results"]] == expected


@pytest.mark.parametrize(
    "responses", [{}, {"https://id.twitch.tv/oauth2/token": {"expires_in": 3600}}], ids=["unreachable", "no token"]
)
def test_import_search_without_a_twitch_token_fails_gracefully(logged_in_client, api_responses, responses):
    """When Twitch gives no token for IGDB, the game search says it failed, rather than breaking the page."""
    api_responses.update(responses)

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": "igdb", "q": "dune"})

    assert response.context["error"] == "Search failed"


def test_import_search_failure_is_logged_once(logged_in_client, api_responses, caplog):
    """A source that cannot be reached is logged once, by its client, rather than by every layer it goes through."""
    response = logged_in_client.get(reverse("import_search_htmx"), {"source": "musicbrainz", "q": "dune"})

    assert response.context["error"] == "Search failed"
    assert [record.levelname for record in caplog.records if record.levelno >= logging.WARNING] == ["WARNING"]


def _make_ol(title, year=2020):
    return OpenLibraryResult(work_key=f"/works/OL{title}W", title=title, authors=["OL Author"], year=year, cover_id=1)


def _make_gb(title, year=2020):
    return GoogleBooksResult(
        volume_id=f"vol-{title}", title=title, authors=["GB Author"], year=year, thumbnail_url=None
    )


@pytest.fixture
def book_clients(monkeypatch):
    """Replace the OpenLibrary and Google Books clients of the book search by mocks, returned in that order."""
    openlibrary, googlebooks = MagicMock(), MagicMock()
    monkeypatch.setattr("core.views.imports.get_openlibrary_client", lambda: openlibrary)
    monkeypatch.setattr("core.views.imports.get_googlebooks_client", lambda: googlebooks)
    return openlibrary, googlebooks


def _search_books(client, **params):
    return client.get(reverse("import_search_htmx"), {"source": "books", "q": "test", **params})


def test_search_interleaves_results_leading_with_googlebooks(logged_in_client, book_clients):
    """Merged list alternates sources, Google Books first."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1"), _make_ol("OL2")]
    googlebooks.search_books.return_value = [_make_gb("GB1"), _make_gb("GB2")]

    response = _search_books(logged_in_client)

    assert [r.title for r in response.context["results"]] == ["GB1", "OL1", "GB2", "OL2"]


def test_search_falls_back_when_googlebooks_fails(logged_in_client, book_clients):
    """OpenLibrary results still render when Google Books raises."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1")]
    googlebooks.search_books.side_effect = APIError("boom")

    response = _search_books(logged_in_client)

    assert "error" not in response.context
    assert [r.title for r in response.context["results"]] == ["OL1"]
    assert "Google Books" in response.context["notice"]


def test_search_falls_back_when_openlibrary_fails(logged_in_client, book_clients):
    """Google Books results still render when OpenLibrary raises."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.side_effect = APIError("boom")
    googlebooks.search_books.return_value = [_make_gb("GB1")]

    response = _search_books(logged_in_client)

    assert "error" not in response.context
    assert [r.title for r in response.context["results"]] == ["GB1"]
    assert "OpenLibrary" in response.context["notice"]


def test_search_surfaces_error_only_when_both_sources_fail(logged_in_client, book_clients):
    """The search fails only when neither source could be searched."""
    for book_client in book_clients:
        book_client.search_books.side_effect = APIError("boom")

    response = _search_books(logged_in_client)

    assert response.context["error"] == "Search failed"
    assert response.context["results"] == []


def test_search_preserves_media_id_and_query_in_context(logged_in_client, book_clients):
    """The results keep the media being edited and the query, for their import links."""
    for book_client in book_clients:
        book_client.search_books.return_value = []

    response = _search_books(logged_in_client, q="hello", media_id="42")

    assert response.context["media_id"] == "42"
    assert response.context["query"] == "hello"


def test_search_without_googlebooks_says_it_is_not_configured(logged_in_client, book_clients, monkeypatch):
    """Without Google Books, the book search shows the results of OpenLibrary, and says how to add Google Books."""
    openlibrary, _googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1")]
    monkeypatch.setattr("core.views.imports.get_googlebooks_client", lambda: None)

    response = _search_books(logged_in_client)

    assert [r.title for r in response.context["results"]] == ["OL1"]
    assert "GOOGLE_BOOKS_API_KEY" in response.context["notice"]
    assert response.context["notice"] in response.content.decode()


@pytest.fixture
def musicbrainz_client(monkeypatch):
    """Replace the MusicBrainz client of the music search by a mock."""
    client = MagicMock()
    monkeypatch.setattr("core.views.imports.get_musicbrainz_client", lambda: client)
    return client


def _search_music(client, **params):
    return client.get(reverse("import_search_htmx"), {"source": "musicbrainz", **params})


def test_returns_search_results(logged_in_client, musicbrainz_client):
    """The music search shows the releases found by MusicBrainz."""
    musicbrainz_client.search_releases.return_value = [
        MusicBrainzResult(
            mbid="test-mbid-123",
            title="Abbey Road",
            artists=["The Beatles"],
            year=1969,
            country="GB",
            label="Apple Records",
        )
    ]

    response = _search_music(logged_in_client, q="abbey road")

    assert [result.title for result in response.context["results"]] == ["Abbey Road"]


def test_handles_api_error_gracefully(logged_in_client, musicbrainz_client):
    """Handles API errors gracefully and shows error message."""
    musicbrainz_client.search_releases.side_effect = APIError("API Error")

    response = _search_music(logged_in_client, q="test query")

    assert response.context["error"] == "Search failed"


def test_preserves_media_id_and_query_in_context(logged_in_client, musicbrainz_client):
    """The results keep the media being edited and the query, for their import links."""
    musicbrainz_client.search_releases.return_value = []

    response = _search_music(logged_in_client, q="test", media_id="42")

    assert response.context["media_id"] == "42"
    assert response.context["query"] == "test"
