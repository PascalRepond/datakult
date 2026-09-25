"""
Tests for core.forms module.

These tests verify the behavior of the MediaForm.
"""

import json
import re

import pytest
from django.urls import reverse
from django.utils import translation

from core.forms import MediaForm
from core.models import Media
from tests.helpers import media_form_data


@pytest.mark.parametrize("field_name", ["title", "media_type"])
def test_title_and_media_type_are_required(db, field_name):
    """A media cannot be saved without a title nor without a media type."""
    data = media_form_data()
    del data[field_name]

    assert list(MediaForm(data=data).errors) == [field_name]


def test_review_date_placeholder_shows_accepted_formats(db):
    """The review date placeholder lists the formats the partial date field accepts, in the active language."""
    placeholder = str(MediaForm().fields["review_date"].widget.attrs["placeholder"])
    with translation.override("fr"):
        translated = str(MediaForm()["review_date"])

    assert "YYYY-MM" in placeholder
    assert "MM-YYYY" not in placeholder
    assert 'placeholder="AAAA, AAAA-MM ou AAAA-MM-JJ"' in translated


def test_only_free_text_fields_are_validated_as_they_are_typed(db):
    """Only the fields whose typed value can be invalid are validated live, each showing its error below it."""
    form = MediaForm()

    validated = {name for name, field in form.fields.items() if "hx-post" in field.widget.attrs}

    assert validated == {"title", "external_uri", "pub_year", "review_date"}
    for field_name in validated:
        attrs = form.fields[field_name].widget.attrs
        assert attrs["hx-post"] == reverse("media_validate_field")
        assert attrs["hx-target"] == f"#error-{field_name}"
        assert json.loads(attrs["hx-vals"]) == {"field_name": field_name}


def test_score_widget_lists_every_verdict(db):
    """The score is picked among radios showing every verdict with its ring, and a radio to leave it unrated."""
    rated = str(MediaForm(initial={"score": 8})["score"])
    unrated = str(MediaForm()["score"])

    assert rated.count('type="radio"') == 11
    for label in dict(Media.score.field.choices).values():
        assert str(label) in rated
    assert re.search(r'type="radio"\s+name="score"\s+value="8"[^>]*\schecked', rated)
    assert re.search(r'type="radio"\s+name="score"\s+value=""[^>]*\schecked', unrated)


def test_form_saves_the_picked_score(db):
    """The score of the checked radio is saved, and the unrated radio clears it."""
    assert MediaForm(data=media_form_data(score="8")).save().score == 8
    assert MediaForm(data=media_form_data(score="")).save().score is None


def test_cover_widget_brings_its_script_as_form_media(db):
    """The cover widget declares its script as form media, rather than inlining scripts and handlers."""
    form = MediaForm()
    html = str(form["cover"])

    assert "<script" not in html
    assert not re.search(r"\son(click|change)=", html)
    assert "js/cover_input.js" in str(form.media)
