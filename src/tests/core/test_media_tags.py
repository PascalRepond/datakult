"""
Tests for core.templatetags.media_tags module.

These tests verify the custom template tags and filters used by the media templates.
"""

import pytest

from core.templatetags.media_tags import has_filters


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", False),
        ("?sort=-score", False),
        ("?tag=", False),
        ("?tag=3", True),
        ("?contributor=1", True),
        ("?status=PLANNED", True),
    ],
)
def test_has_filters(rf, query, expected):
    """has_filters is true only when a filter parameter has a value."""
    assert has_filters(rf.get(f"/{query}")) is expected
