"""
Tests for core.stats module.

These tests verify the aggregations used by the statistics dashboard.
"""

import pytest

from core import stats
from core.models import Agent, Media, MediaType


@pytest.fixture
def all_media(db):
    """Unfiltered media queryset passed to the stats functions."""
    return Media.objects.all()


def test_filter_by_year_includes_all_precisions(media_factory, all_media):
    """Year, month and day precision dates within the year are kept; others and undated media are not."""
    media_factory(title="Before", review_date="2021-12-31")
    media_factory(title="Year", review_date="2022")
    media_factory(title="Month", review_date="2022-06")
    media_factory(title="Last day", review_date="2022-12-31")
    media_factory(title="After", review_date="2023-01")
    media_factory(title="Undated")

    result = stats.filter_by_year(all_media, 2022)

    assert sorted(result.values_list("title", flat=True)) == ["Last day", "Month", "Year"]


def test_filter_by_year_below_1000(media_factory, all_media):
    """Years below 1000 match their zero-padded review dates."""
    media_factory(review_date="0999-05")

    assert stats.filter_by_year(all_media, 999).count() == 1


def test_filter_by_year_none_keeps_everything(media_factory, all_media):
    """Without a year, the queryset is left untouched, undated media included."""
    media_factory(review_date="2020")
    media_factory()

    assert stats.filter_by_year(all_media).count() == 2


def test_available_years_descending(media_factory, all_media):
    """Review years are returned newest first, without duplicates."""
    media_factory(review_date="2022")
    media_factory(review_date="2024-01")
    media_factory(review_date="2024-06-01")
    media_factory()

    assert stats.available_years(all_media) == [2024, 2022]


def test_adjacent_years():
    """Previous and next years are the closest available ones, None when there is none or no year is selected."""
    years = [2024, 2021, 2020]

    assert stats.adjacent_years(years, 2021) == (2020, 2024)
    assert stats.adjacent_years(years, 2022) == (2021, 2024)
    assert stats.adjacent_years(years, 2024) == (2021, None)
    assert stats.adjacent_years(years, 2020) == (None, 2021)
    assert stats.adjacent_years(years, None) == (None, None)


def test_count_per_type_lists_every_type(media_factory, all_media):
    """Every media type is listed in the model choices order, with zero for types without media."""
    media_factory(media_type="FILM")
    media_factory(media_type="FILM")
    media_factory(media_type="BOOK")

    result = stats.count_per_type(all_media)

    assert [row["media_type"] for row in result] == MediaType.values
    counts = {row["media_type"]: row["count"] for row in result}
    assert (counts["BOOK"], counts["FILM"], counts["GAME"]) == (1, 2, 0)
    assert result[0]["label"] == "Book"


def test_count_per_year_zero_fills_gaps(media_factory, all_media):
    """Dated media are counted per review year, with empty years in between."""
    media_factory(review_date="2022-05-01")
    media_factory(review_date="2024")
    media_factory(review_date="2024-03")
    media_factory()

    result = stats.count_per_year(all_media)

    assert [(row["label"], row["count"]) for row in result] == [(2022, 1), (2023, 0), (2024, 2)]
    assert [row["pct"] for row in result] == [50, 0, 100]


def test_count_per_year_empty(all_media):
    """No dated media returns an empty list."""
    assert stats.count_per_year(all_media) == []


def test_count_per_month_counts_year_only_dates_in_january(media_factory, all_media):
    """Monthly counts cover 12 months of the given year, year-only dates falling in January."""
    media_factory(review_date="2024")
    media_factory(review_date="2024-03")
    media_factory(review_date="2024-03-15")
    media_factory(review_date="2024-12-31")
    media_factory(review_date="2023-03-15")

    result = stats.count_per_month(all_media, 2024)

    counts = [row["count"] for row in result]
    assert len(result) == 12
    assert counts[0] == 1
    assert counts[2] == 2
    assert counts[11] == 1
    assert sum(counts) == 4


def test_count_per_decade_groups_early_works_and_zero_fills(media_factory, all_media):
    """Works before 1900 share a bar, decades from 1900 to the latest are zero-filled, undated releases are skipped."""
    for pub_year in (-500, 1899, 1900, 1909, 1925, 2024, None):
        media_factory(pub_year=pub_year)

    result = stats.count_per_decade(all_media)

    assert [(row["label"], row["count"]) for row in result] == [
        ("<1900", 2),
        (1900, 2),
        (1910, 0),
        (1920, 1),
        *[(decade, 0) for decade in range(1930, 2020, 10)],
        (2020, 1),
    ]
    assert [(row["title"], row["start"], row["end"]) for row in result[:2]] == [
        ("Before 1900", None, 1899),
        ("1900 → 1909", 1900, 1909),
    ]


def test_count_per_decade_empty(media_factory, all_media):
    """No media with a release year returns an empty list."""
    media_factory()

    assert stats.count_per_decade(all_media) == []


def test_score_distribution_has_ten_buckets(media_factory, all_media):
    """Scores are bucketed from 1 to 10, including empty buckets."""
    media_factory(score=8)
    media_factory(score=8)
    media_factory(score=3)

    result = stats.score_distribution(all_media)

    assert [row["label"] for row in result] == list(range(1, 11))
    assert result[7]["count"] == 2
    assert result[2]["count"] == 1
    assert result[7]["pct"] == 100
    assert result[7]["title"] == "Really enjoyed"


def test_contributor_rankings_most_frequent(media_factory):
    """Contributors are ranked by media count, then by name ignoring case, out of the given media only."""
    alpha, beta, gamma = (Agent.objects.create(name=name) for name in ("alpha", "Beta", "gamma"))
    for contributors in ([alpha, gamma], [beta, gamma], [gamma]):
        media_factory(media_type="BOOK", contributors=contributors)
    for _ in range(2):
        media_factory(media_type="FILM", contributors=[alpha])

    result = stats.contributor_rankings(Media.objects.filter(media_type="BOOK"))["most_frequent"]

    assert [(row["name"], row["count"]) for row in result] == [("gamma", 3), ("alpha", 1), ("Beta", 1)]


def test_contributor_rankings_best_rated(media_factory, all_media):
    """Contributors with enough media are ranked by average score, then by media count."""
    for name, scores in {"Few": (10, 10), "Good": (6, 7, 8), "Better": (9, 8, 7), "Frequent": (7, 7, 7, 7)}.items():
        agent = Agent.objects.create(name=name)
        for score in scores:
            media_factory(score=score, contributors=[agent])

    result = stats.contributor_rankings(all_media)["best_rated"]

    assert [(row["name"], row["average_score"], row["count"]) for row in result] == [
        ("Better", 8, 3),
        ("Frequent", 7, 4),
        ("Good", 7, 3),
    ]


def test_contributor_rankings_keep_the_top_entries(media_factory, all_media):
    """Rankings stop at their size."""
    media_factory(contributors=[Agent.objects.create(name=f"Agent {i}") for i in range(stats.RANKING_SIZE + 1)])

    assert len(stats.contributor_rankings(all_media)["most_frequent"]) == stats.RANKING_SIZE
