"""
Tests for core.forms module.

These tests verify the behavior of the MediaForm.
"""

import re

from django.utils.functional import Promise

from core.forms import MediaForm
from core.models import Agent, Media


def test_form_valid_with_required_fields(db):
    """Form is valid with only required fields."""
    data = {
        "title": "Test Book",
        "media_type": "BOOK",
        "status": "PLANNED",
    }
    form = MediaForm(data=data)

    assert form.is_valid(), form.errors


def test_form_invalid_without_title(db):
    """Form is invalid without a title."""
    data = {
        "media_type": "BOOK",
        "status": "PLANNED",
    }
    form = MediaForm(data=data)

    assert not form.is_valid()
    assert "title" in form.errors


def test_form_invalid_without_media_type(db):
    """Form is invalid without a media type."""
    data = {
        "title": "Test",
        "status": "PLANNED",
    }
    form = MediaForm(data=data)

    assert not form.is_valid()
    assert "media_type" in form.errors


def test_form_accepts_valid_pub_year(db):
    """Form accepts a valid publication year."""
    data = {
        "title": "Test",
        "media_type": "BOOK",
        "status": "PLANNED",
        "pub_year": 2024,
    }
    form = MediaForm(data=data)

    assert form.is_valid(), form.errors


def test_form_rejects_invalid_pub_year(db):
    """Form rejects a publication year outside valid range."""
    data = {
        "title": "Test",
        "media_type": "BOOK",
        "status": "PLANNED",
        "pub_year": -5000,
    }
    form = MediaForm(data=data)

    assert not form.is_valid()
    assert "pub_year" in form.errors


def test_form_saves_with_contributors(db):
    """Form can save a media with existing contributors."""
    agent = Agent.objects.create(name="Author")
    data = {
        "title": "Test",
        "media_type": "BOOK",
        "status": "PLANNED",
        "contributors": [agent.pk],
    }
    form = MediaForm(data=data)

    assert form.is_valid(), form.errors
    media = form.save()
    assert agent in media.contributors.all()


def test_form_updates_existing_media(db):
    """Form can update an existing media instance."""
    media = Media.objects.create(
        title="Original",
        media_type="BOOK",
        status="PLANNED",
    )
    data = {
        "title": "Updated",
        "media_type": "FILM",
        "status": "COMPLETED",
    }
    form = MediaForm(data=data, instance=media)

    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.pk == media.pk
    assert updated.title == "Updated"
    assert updated.media_type == "FILM"


def test_form_accepts_all_media_types(db):
    """Form accepts all valid media types."""
    valid_types = ["BOOK", "GAME", "MUSIC", "COMIC", "FILM", "TV", "PERF", "BROADCAST"]

    for media_type in valid_types:
        data = {
            "title": f"Test {media_type}",
            "media_type": media_type,
            "status": "PLANNED",
        }
        form = MediaForm(data=data)
        assert form.is_valid(), f"Failed for {media_type}: {form.errors}"


def test_form_accepts_all_statuses(db):
    """Form accepts all valid statuses."""
    valid_statuses = ["PLANNED", "IN_PROGRESS", "COMPLETED", "PAUSED", "DNF"]

    for status in valid_statuses:
        data = {
            "title": f"Test {status}",
            "media_type": "BOOK",
            "status": status,
        }
        form = MediaForm(data=data)
        assert form.is_valid(), f"Failed for {status}: {form.errors}"


def test_form_accepts_all_scores(db):
    """Form accepts all valid scores."""
    for score in range(1, 11):
        data = {
            "title": f"Test score {score}",
            "media_type": "BOOK",
            "status": "COMPLETED",
            "score": score,
        }
        form = MediaForm(data=data)
        assert form.is_valid(), f"Failed for score {score}: {form.errors}"


def test_review_date_placeholder_shows_accepted_formats(db):
    """The review date placeholder lists the formats the partial date field accepts."""
    placeholder = str(MediaForm().fields["review_date"].widget.attrs["placeholder"])

    assert "YYYY-MM" in placeholder
    assert "MM-YYYY" not in placeholder


def test_placeholders_follow_active_language(db):
    """Placeholders are translated at render time, in the language of the request, and not once at import."""
    for field_name in ["pub_year", "review_date"]:
        assert isinstance(MediaForm().fields[field_name].widget.attrs["placeholder"], Promise)


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
    data = {"title": "Rated", "media_type": "BOOK", "status": "PLANNED"}

    assert MediaForm(data={**data, "score": "8"}).save().score == 8
    assert MediaForm(data={**data, "score": ""}).save().score is None


def test_cover_widget_brings_its_script_as_form_media(db):
    """The cover widget declares its script as form media, rather than inlining scripts and handlers."""
    form = MediaForm()
    html = str(form["cover"])

    assert "<script" not in html
    assert not re.search(r"\son(click|change)=", html)
    assert "js/cover_input.js" in str(form.media)
