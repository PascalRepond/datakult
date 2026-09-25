"""
Tests for core.htmx_validation module.

These tests verify the live validation of the media form fields.
"""

import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"field_name": "title", "title": ""},
            '<span class="label-text-alt text-error">This field is required.</span>',
        ),
        ({"field_name": "title", "title": "Valid Title"}, ""),
        *[({"field_name": field_name}, "") for field_name in ["cover", "contributors", "review", "score"]],
        ({"field_name": "unknown"}, ""),
    ],
)
def test_validate_media_field_returns_the_error_of_that_field(logged_in_client, data, expected):
    """A field is validated alone: its error if it has one, nothing for optional fields left empty or unknown fields."""
    response = logged_in_client.post(reverse("media_validate_field"), data)

    assert response.content.decode() == expected
