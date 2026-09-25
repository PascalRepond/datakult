"""
Tests for core.views.stats: the statistics page.
"""

import pytest
from django.urls import reverse

from core.views.stats import STATS_COVERS_PER_PAGE


def test_stats_only_counts_rated_media(logged_in_client, media_factory):
    """Only rated media are counted, whatever their status."""
    media_factory(status="COMPLETED", review_date="2024", score=8)
    media_factory(status="DNF", review_date="2024", score=4)
    media_factory(status="COMPLETED", review_date="2023")

    response = logged_in_client.get(reverse("stats"))

    assert response.context["overview"] == {"count": 2, "average_score": 6.0}
    assert response.context["years"] == [2024]
    assert sum(row["count"] for row in response.context["type_counts"]) == 2


def test_stats_all_years_shows_yearly_chart(logged_in_client, media_factory):
    """Without a year, the yearly chart replaces the monthly one."""
    media_factory(review_date="2023-03-15", score=8)
    media_factory(review_date="2024-03-15", score=6)

    response = logged_in_client.get(reverse("stats"))

    assert [row["label"] for row in response.context["per_year"]] == [2023, 2024]
    assert response.context["per_month"] is None


def test_stats_year_shows_monthly_chart(logged_in_client, media_factory):
    """Selecting a year restricts the page to that year and shows the monthly chart instead of the yearly one."""
    media_factory(review_date="2023-06", score=2)
    media_factory(review_date="2024-03-15", score=8)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    assert response.context["year"] == 2024
    assert response.context["overview"] == {"count": 1, "average_score": 8.0}
    assert response.context["per_year"] is None
    assert response.context["per_month"][2]["count"] == 1


def test_stats_year_navigation(logged_in_client, media_factory):
    """The selected year comes with the previous and next years that have rated media."""
    for review_date in ("2018", "2020-05", "2023-01-01"):
        media_factory(review_date=review_date, score=5)

    response = logged_in_client.get(reverse("stats"), {"year": "2020"})

    assert (response.context["previous_year"], response.context["next_year"]) == (2018, 2023)


@pytest.mark.parametrize("params", [{"type": "BOOK"}, {"type": "BOOK", "year": "2024"}])
def test_stats_years_follow_the_media_type(logged_in_client, media_factory, params):
    """The year picker only offers the years with rated media of the selected type, with or without a year."""
    media_factory(media_type="BOOK", review_date="2020", score=5)
    media_factory(media_type="FILM", review_date="2022", score=5)
    media_factory(media_type="BOOK", review_date="2024-06", score=5)

    response = logged_in_client.get(reverse("stats"), params)

    assert response.context["years"] == [2024, 2020]


def test_stats_type_filter(logged_in_client, media_factory):
    """A media type restricts the charts, while the type counters still show every type."""
    media_factory(media_type="BOOK", review_date="2024", score=9)
    media_factory(media_type="FILM", review_date="2024", score=3)

    response = logged_in_client.get(reverse("stats"), {"type": "FILM"})

    assert (response.context["media_type"], response.context["media_type_label"]) == ("FILM", "Film")
    assert response.context["overview"] == {"count": 1, "average_score": 3.0}
    assert response.context["score_distribution"][2]["count"] == 1
    assert response.context["score_distribution"][8]["count"] == 0
    counts = {row["media_type"]: row["count"] for row in response.context["type_counts"]}
    assert (counts["BOOK"], counts["FILM"]) == (1, 1)


@pytest.mark.parametrize("year", ["abc", "0", "9999", pytest.param("1" * 5000, id="oversized")])
def test_stats_invalid_filters_are_ignored(logged_in_client, media_factory, year):
    """Invalid type and year parameters, years out of the review date range included, fall back to everything."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats"), {"year": year, "type": "NOPE"})

    assert response.context["year"] is None
    assert response.context["media_type"] is None
    assert response.context["overview"]["count"] == 1


def test_stats_covers_first_page(logged_in_client, media_factory):
    """The first page of covers shows rated media only, best scores first, then latest reviews."""
    media_factory(title="Unrated", review_date="2024-12-31")
    for day in range(1, STATS_COVERS_PER_PAGE + 2):
        media_factory(title=f"Day {day}", review_date=f"2024-01-{day % 28 + 1:02d}", score=5)
    older_best = media_factory(title="Older best", review_date="2023-05", score=9)
    newer_best = media_factory(title="Newer best", review_date="2024-02", score=9)
    top = media_factory(title="Top", review_date="2020", score=10)

    response = logged_in_client.get(reverse("stats"))

    covers = response.context["covers"]
    assert len(covers) == STATS_COVERS_PER_PAGE
    assert list(covers[:3]) == [top, newer_best, older_best]
    assert 'aria-label="Top, Score: 10 out of 10"' in response.content.decode("utf-8")
    assert "Unrated" not in [media.title for media in covers.object_list]
    assert covers.has_next()


def test_stats_covers_htmx_returns_next_page_with_filters(logged_in_client, media_factory):
    """The covers endpoint returns the requested page, keeping the year and type filters."""
    for _ in range(STATS_COVERS_PER_PAGE + 1):
        media_factory(media_type="FILM", review_date="2024", score=5)
    media_factory(media_type="BOOK", review_date="2024", score=5)
    media_factory(media_type="FILM", review_date="2023", score=5)

    response = logged_in_client.get(reverse("stats_covers_htmx"), {"year": "2024", "type": "FILM", "page": "2"})

    assert "partials/stats/covers_page.html" in [t.name for t in response.templates]
    covers = response.context["covers"]
    assert covers.number == 2
    assert covers.paginator.count == STATS_COVERS_PER_PAGE + 1
    assert len(covers) == 1


def test_stats_covers_htmx_out_of_range_page_is_empty(logged_in_client, media_factory):
    """A page past the last one adds nothing, instead of repeating the covers already shown."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats_covers_htmx"), {"page": "2"})

    assert response.status_code == 200
    assert not response.content


@pytest.mark.parametrize(
    ("params", "message"),
    [({}, "No rated media yet."), ({"type": "GAME"}, "No rated media match the selected filters.")],
)
def test_stats_without_covers_message_depends_on_filters(logged_in_client, params, message):
    """Without covers, the message tells an empty collection apart from filters matching nothing."""
    response = logged_in_client.get(reverse("stats"), params)

    assert message in response.content.decode("utf-8")


def _home_count(client, url):
    """Number of media listed on the home page at `url`."""
    return client.get(url).context["page_obj"].paginator.count


def test_stats_year_bars_link_to_stats_of_that_year(logged_in_client, media_factory):
    """Each yearly bar links to the stats page filtered on that year, keeping the selected media type."""
    media_factory(media_type="BOOK", review_date="2016", score=7)
    media_factory(media_type="BOOK", review_date="2016-12-31", score=7)
    media_factory(media_type="FILM", review_date="2016-06-01", score=7)
    media_factory(media_type="BOOK", review_date="2017-01-01", score=7)

    bar = logged_in_client.get(reverse("stats"), {"type": "BOOK"}).context["per_year"][0]
    response = logged_in_client.get(bar["url"])

    assert bar["label"] == 2016
    assert (response.context["year"], response.context["media_type"]) == (2016, "BOOK")
    assert response.context["overview"]["count"] == bar["count"] == 2


def test_stats_month_bars_link_to_filtered_home(logged_in_client, media_factory):
    """Each monthly bar links to the media list filtered on that month."""
    media_factory(review_date="2024-02", score=7)
    media_factory(review_date="2024-02-29", score=7)
    media_factory(review_date="2024-03-01", score=7)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    february = response.context["per_month"][1]
    assert "review_from=2024-02-01" in february["url"]
    assert "review_to=2024-02-29" in february["url"]
    assert _home_count(logged_in_client, february["url"]) == february["count"] == 2


def test_stats_score_bars_link_to_filtered_home(logged_in_client, media_factory):
    """Each score bar links to the media list filtered on that score, keeping the selected year and type."""
    media_factory(media_type="GAME", review_date="2026-03", score=4)
    media_factory(media_type="GAME", review_date="2026", score=4)
    media_factory(media_type="GAME", review_date="2025-12-31", score=4)
    media_factory(media_type="FILM", review_date="2026-03", score=4)

    response = logged_in_client.get(reverse("stats"), {"year": "2026", "type": "GAME"})

    bar = response.context["score_distribution"][3]
    assert bar["label"] == 4
    assert _home_count(logged_in_client, bar["url"]) == bar["count"] == 2
