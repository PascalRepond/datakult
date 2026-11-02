"""Fill page counts command."""

import re
import time
from urllib.parse import parse_qs, urlsplit

from django.core.management.base import BaseCommand

from core.models import PAGED_TYPES, Media
from core.services.base import APIError
from core.services.googlebooks import get_googlebooks_client
from core.services.openlibrary import get_openlibrary_client

# OpenLibrary asks for about one request per second
REQUEST_DELAY = 1  # seconds
OPENLIBRARY_WORK_PATTERN = re.compile(r"openlibrary\.org/works/(OL\d+W)")
# Hosts of the Google Books links, whose id query names their volume
GOOGLEBOOKS_HOSTS = {"books.google.com", "play.google.com"}
# Series and subtitles, which the sources tend to name differently, are left out of the searched title
TITLE_SUFFIX_PATTERN = re.compile(r"\s*[(:].*")
# OpenLibrary results looked through for a page count, which the first editions or variants of a work may lack
OPENLIBRARY_RESULTS = 5


def _fielded_query(**terms):
    """Return a query searching every non-empty term in its field, such as title:"Dune"."""
    quoted = {field: term.replace('"', "") for field, term in terms.items() if term}
    return " ".join(f'{field}:"{term}"' for field, term in quoted.items())


class Command(BaseCommand):
    """Fill the page count of the books and comics without one, from the source of their link or a search."""

    help = "Fill the page count of the books and comics without one, from OpenLibrary and Google Books"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument("--dry-run", action="store_true", help="Show the page counts found without saving them")

    def handle(self, **options):
        """Look for the page count of every book and comic without one, and save those found."""
        self.openlibrary = get_openlibrary_client()
        self.googlebooks = get_googlebooks_client()
        missing = Media.objects.filter(media_type__in=PAGED_TYPES, page_count__isnull=True)
        found_count, not_found = 0, []

        for media in missing.prefetch_related("contributors").order_by("title"):
            if found := self._find(media):
                media.page_count, match = found
                found_count += 1
                self.stdout.write(f"{media.title}: {media.page_count} pages, found as {match}")
                if not options["dry_run"]:
                    # Only the page count is saved, so that the media is not marked as updated
                    media.save(update_fields=["page_count"])
            else:
                not_found.append(media.title)

        verb = "Found" if options["dry_run"] else "Filled"
        self.stdout.write(self.style.SUCCESS(f"✓ {verb} the page count of {found_count} media"))
        if not_found:
            self.stdout.write(
                self.style.WARNING(f"No page count found for {len(not_found)} media, to fill in by hand:")
            )
            for title in not_found:
                self.stdout.write(f"  {title}")

    def _find(self, media):
        """Return the page count of a media and the title it was found as, or None."""
        url = urlsplit(media.external_uri)
        contributor = next(iter(media.contributors.all()), None)
        title = TITLE_SUFFIX_PATTERN.sub("", media.title)
        # The surname alone, as the sources write initials differently, such as George R. R. Martin
        author = contributor.name.split()[-1] if contributor else ""

        # The work or volume of the link is asked first; works may lack a page count that another record of them has
        found = None
        if work := OPENLIBRARY_WORK_PATTERN.search(media.external_uri):
            found = self._search_openlibrary(f"key:/works/{work[1]}")
        elif url.hostname in GOOGLEBOOKS_HOSTS and (volume_id := parse_qs(url.query).get("id")):
            found = self._googlebooks_volume(volume_id[0])
        return (
            found
            or self._search_openlibrary(_fielded_query(title=title, author=author))
            or self._search_googlebooks(_fielded_query(intitle=title, inauthor=author))
        )

    @staticmethod
    def _ask(client, question):
        """Return the answer of a source to `question(client)`, or None when the source is not configured or failed."""
        if client is None:
            return None
        try:
            return question(client)
        except APIError:
            return None

    def _search_openlibrary(self, query):
        """Return the page count and title of the first OpenLibrary work found by a query with one, or None."""
        time.sleep(REQUEST_DELAY)
        results = self._ask(self.openlibrary, lambda client: client.search_books(query, limit=OPENLIBRARY_RESULTS))
        work = next((result for result in results or [] if result.page_count), None)
        return (work.page_count, work.title) if work else None

    def _googlebooks_volume(self, volume_id):
        """Return the page count and title of a Google Books volume, or None."""
        details = self._ask(self.googlebooks, lambda client: client.get_volume_details(volume_id))
        return (details["page_count"], details["title"]) if details and details["page_count"] else None

    def _search_googlebooks(self, query):
        """Return the page count and title of the first Google Books volume found by a query, or None."""
        results = self._ask(self.googlebooks, lambda client: client.search_books(query, limit=1))
        # The search results of the client hold no page count, which the details of the volume give
        return self._googlebooks_volume(results[0].volume_id) if results else None
