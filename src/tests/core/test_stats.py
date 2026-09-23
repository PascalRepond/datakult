"""
Tests for core.stats module.

These tests verify the aggregations used by the statistics dashboard.
"""

import pytest

from core import stats
from core.models import Media


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

    assert [row["media_type"] for row in result] == [key for key, _ in Media.media_type.field.choices]
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


def test_overview(media_factory, all_media):
    """Overview counts media and averages their scores."""
    media_factory(score=8)
    media_factory(score=6)

    assert stats.overview(all_media) == {"count": 2, "average_score": 7.0}


def test_overview_empty(all_media):
    """Overview handles an empty queryset."""
    assert stats.overview(all_media) == {"count": 0, "average_score": None}
