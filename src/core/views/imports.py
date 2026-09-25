"""Views searching the external metadata sources, and helpers filling the media form with their metadata."""

import itertools
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from core.import_results import from_googlebooks, from_igdb, from_musicbrainz, from_openlibrary, from_tmdb
from core.models import MediaType
from core.services.base import MIN_QUERY_LENGTH, APIError
from core.services.googlebooks import get_googlebooks_client
from core.services.igdb import get_igdb_client
from core.services.musicbrainz import get_musicbrainz_client
from core.services.openlibrary import get_openlibrary_client
from core.services.tmdb import get_tmdb_client

DEFAULT_TMDB_LANGUAGE = "en-US"
# Metadata sources of the import page: value, tab label, icon
IMPORT_SOURCES = [
    ("tmdb", gettext_lazy("Movies & TV"), "clapperboard"),
    ("igdb", gettext_lazy("Video games"), "gamepad-2"),
    ("books", gettext_lazy("Books"), "book-open"),
    ("musicbrainz", gettext_lazy("Music"), "disc-3"),
]
# Source searched first when importing into a media of each type
DEFAULT_IMPORT_SOURCES = {
    MediaType.FILM: "tmdb",
    MediaType.TV: "tmdb",
    MediaType.GAME: "igdb",
    MediaType.BOOK: "books",
    MediaType.COMIC: "books",
    MediaType.MUSIC: "musicbrainz",
}
# Media type of the works of each kind that the sources give
IMPORT_MEDIA_TYPES = {
    "movie": MediaType.FILM,
    "tv": MediaType.TV,
    "game": MediaType.GAME,
    "book": MediaType.BOOK,
    "music": MediaType.MUSIC,
}
TMDB_LANGUAGES = [
    ("en-US", "English"),
    ("fr-FR", "Français"),
    ("de-DE", "Deutsch"),
    ("es-ES", "Español"),
    ("it-IT", "Italiano"),
    ("pt-PT", "Português"),
    ("ja-JP", "日本語"),
]
MAX_SEARCH_RESULTS = 15
IMPORT_RESULTS_TEMPLATE = "partials/import/import_results.html"
# Client downloading the covers of each image server
_COVER_SOURCES = (
    ("image.tmdb.org", get_tmdb_client),
    ("images.igdb.com", get_igdb_client),
    ("covers.openlibrary.org", get_openlibrary_client),
    ("books.google.com", get_googlebooks_client),
    ("coverartarchive.org", get_musicbrainz_client),
)


@login_required
def media_import(request):
    """Display search page for importing media metadata."""
    context = {
        "media_id": request.GET.get("media_id"),
        "default_source": DEFAULT_IMPORT_SOURCES.get(request.GET.get("media_type"), "tmdb"),
        "default_query": request.GET.get("title", ""),
        "import_sources": IMPORT_SOURCES,
        "tmdb_languages": TMDB_LANGUAGES,
        "tmdb_language": DEFAULT_TMDB_LANGUAGE,
    }
    return render(request, "base/media_import.html", context)


def _results_context(request, **extra):
    """Return the context of the results of a search, empty until the query is searched."""
    return {"results": [], "media_id": request.GET.get("media_id"), "query": request.GET.get("q", "").strip(), **extra}


def _search_source(request, get_client, search, not_configured="", **extra_context):
    """
    Render the results of a search of one source, which `search(client, query, media_id)` returns as import results.

    Without a client, the source is not configured: the results then show `not_configured`.
    """
    context = _results_context(request, **extra_context)
    if len(context["query"]) >= MIN_QUERY_LENGTH:
        if (client := get_client()) is None:
            context["error"] = not_configured
        else:
            try:
                context["results"] = search(client, context["query"], context["media_id"])
            except APIError:
                context["error"] = _("Search failed")
    return render(request, IMPORT_RESULTS_TEMPLATE, context)


def _search_tmdb(request):
    """Search TMDB for movies and TV shows, in the language picked on the import page."""
    lang = request.GET.get("lang", DEFAULT_TMDB_LANGUAGE)

    def search(client, query, media_id):
        found = client.search_multi(query, language=lang)[:MAX_SEARCH_RESULTS]
        return [from_tmdb(result, media_id, lang) for result in found]

    return _search_source(request, get_tmdb_client, search, _("TMDB API key not configured"), lang=lang)


def _search_igdb(request):
    """Search IGDB for video games."""

    def search(client, query, media_id):
        return [from_igdb(result, media_id) for result in client.search_games(query, limit=MAX_SEARCH_RESULTS)]

    return _search_source(request, get_igdb_client, search, _("IGDB API credentials not configured"))


def _search_musicbrainz(request):
    """Search MusicBrainz for music albums."""

    def search(client, query, media_id):
        return [
            from_musicbrainz(result, media_id) for result in client.search_releases(query, limit=MAX_SEARCH_RESULTS)
        ]

    return _search_source(request, get_musicbrainz_client, search)


def _search_books_source(search_fn, query: str, limit: int) -> tuple[list, bool]:
    """
    Run a book search. Returns (results, ok).

    ok=False means the source errored — the other source can still fill the page.
    """
    try:
        return search_fn(query, limit=limit), True
    except APIError:
        return [], False


def _interleave(*iterables):
    """Round-robin interleave: [a1,a2], [b1,b2,b3] -> [a1,b1,a2,b2,b3]."""
    sentinel = object()
    zipped = itertools.zip_longest(*iterables, fillvalue=sentinel)
    return [item for group in zipped for item in group if item is not sentinel]


def _search_books(request):
    """Search OpenLibrary and Google Books in parallel, and merge their results."""
    context = _results_context(request)
    query, media_id = context["query"], context["media_id"]
    if len(query) < MIN_QUERY_LENGTH:
        return render(request, IMPORT_RESULTS_TEMPLATE, context)

    openlibrary = get_openlibrary_client()
    googlebooks = get_googlebooks_client()

    with ThreadPoolExecutor(max_workers=2) as executor:
        ol_future = executor.submit(_search_books_source, openlibrary.search_books, query, MAX_SEARCH_RESULTS)
        # Without an API key, Google Books is not searched at all
        gb_future = googlebooks and executor.submit(
            _search_books_source, googlebooks.search_books, query, MAX_SEARCH_RESULTS
        )
        ol_results, ol_ok = ol_future.result()
        gb_results, gb_ok = gb_future.result() if gb_future else ([], False)

    # Google Books typically has richer metadata for modern fiction, so we lead with it
    context["results"] = _interleave(
        [from_googlebooks(result, media_id) for result in gb_results],
        [from_openlibrary(result, media_id) for result in ol_results],
    )[:MAX_SEARCH_RESULTS]

    # Tell when the results only come from one of the sources
    if not ol_ok and not gb_ok:
        context["error"] = _("Search failed")
    elif not googlebooks:
        context["notice"] = _("Google Books is not searched, as it needs an API key: set GOOGLE_BOOKS_API_KEY.")
    elif not (ol_ok and gb_ok):
        context["notice"] = _("%(source)s could not be searched: the results only come from the other source.") % {
            "source": "OpenLibrary" if not ol_ok else "Google Books"
        }

    return render(request, IMPORT_RESULTS_TEMPLATE, context)


IMPORT_SEARCHES = {
    "tmdb": _search_tmdb,
    "igdb": _search_igdb,
    "books": _search_books,
    "musicbrainz": _search_musicbrainz,
}


@login_required
def import_search_htmx(request):
    """HTMX view: search the metadata source picked in the tabs of the import page."""
    search = IMPORT_SEARCHES.get(request.GET.get("source"))
    if search is None:
        return HttpResponseBadRequest("Unknown import source")
    return search(request)


def _fetch_details(get_client, fetch):
    """Return the details that `fetch(client)` gets from a source, or None when the source cannot give them."""
    if (client := get_client()) is None:
        return None
    try:
        return fetch(client)
    except APIError, ValueError:  # The source failed, or the request gave an invalid ID
        return None


def fetch_import_data(request) -> dict | None:
    """Fetch the metadata to import from the source whose work the request parameters name, if any."""
    params = request.GET
    if (tmdb_id := params.get("tmdb_id")) and (media_type := params.get("media_type")) in ("movie", "tv"):
        language = params.get("lang", DEFAULT_TMDB_LANGUAGE)
        return _fetch_details(
            get_tmdb_client, lambda client: client.get_full_details(int(tmdb_id), media_type, language=language)
        )
    if igdb_id := params.get("igdb_id"):
        return _fetch_details(get_igdb_client, lambda client: client.get_game_details(int(igdb_id)))
    if openlibrary_key := params.get("openlibrary_key"):
        year = params.get("year", "")
        return _fetch_details(
            get_openlibrary_client,
            lambda client: client.get_work_details(
                openlibrary_key, first_publish_year=int(year) if year.isdigit() else None
            ),
        )
    if googlebooks_id := params.get("googlebooks_id"):
        return _fetch_details(get_googlebooks_client, lambda client: client.get_volume_details(googlebooks_id))
    if musicbrainz_id := params.get("musicbrainz_id"):
        return _fetch_details(get_musicbrainz_client, lambda client: client.get_release_details(musicbrainz_id))
    return None


def import_initial_data(import_data: dict, media=None) -> dict:
    """Return the initial data of the media form filled with the imported metadata, keeping the review of a media."""
    initial_data = {
        "title": import_data.get("title", ""),
        "pub_year": import_data.get("year"),
        "media_type": IMPORT_MEDIA_TYPES.get(import_data.get("media_type"), ""),
        "external_uri": import_data.get("source_url", ""),
    }
    if media:
        # Keep existing values for fields user may have customized
        initial_data |= {
            "status": media.status,
            "score": media.score,
            "review": media.review,
            "review_date": media.review_date,
        }
    return initial_data


def import_suggestions(import_data: dict, media=None) -> tuple[list, list]:
    """Return the imported contributors and tags to suggest, leaving out those that the media already has."""
    known_contributors = {agent.name.lower() for agent in media.contributors.all()} if media else set()
    known_tags = {tag.name.lower() for tag in media.tags.all()} if media else set()
    return (
        [name for name in import_data.get("contributors", []) if name.lower() not in known_contributors],
        [name for name in import_data.get("genres", []) if name.lower() not in known_tags],
    )


def _download_cover(cover_url: str) -> bytes | None:
    """Download cover image from any supported source."""
    for host, get_client in _COVER_SOURCES:
        if host in cover_url:
            client = get_client()
            return client.download_cover(cover_url) if client else None
    return None


def attach_import_cover(request, instance):
    """Download and attach cover from import source if provided, to be compressed like an upload on save."""
    cover_url = request.POST.get("import_cover_url")
    if cover_url and not request.FILES.get("cover") and (cover_bytes := _download_cover(cover_url)):
        instance.cover = ContentFile(cover_bytes, name=f"{instance.title[:50].replace('/', '_')}.jpg")
