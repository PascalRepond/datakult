"""
Tests that the texts users read are translated in French, including the sentences composed with values.
"""

import pytest
from django.urls import reverse
from django.utils import translation

from core.forms import MediaForm
from tests.helpers import media_form_data, messages_of


@pytest.fixture
def french_client(logged_in_client):
    """Return the client of a logged-in user who reads French."""
    logged_in_client.defaults["HTTP_ACCEPT_LANGUAGE"] = "fr"
    return logged_in_client


@pytest.fixture
def dune(media_factory, agent):
    """Create a rated media, with a cover and a contributor."""
    return media_factory(title="Dune", score=7, review_date="2024", cover="covers/dune.jpg", contributors=[agent])


def _missing(response, texts):
    """Return the texts that the page of the response does not contain."""
    content = response.content.decode()
    return [text for text in texts if text not in content]


def test_list_page_is_translated(french_client, dune, saved_view_factory):
    """The labels of the sidebar and of the media cards are translated, with the values they name."""
    saved_view_factory(name="Livres", filter_types=["BOOK"])
    labels = [
        'aria-label="Ouvrir la barre latérale"',
        'aria-label="Fermer la barre latérale"',
        'aria-label="Supprimer Livres"',
        "Supprimer la vue enregistrée",
        'aria-label="Modifier Dune"',
        'alt="Couverture de Dune"',
        'aria-label="Note : 7 sur 10"',
    ]

    response = french_client.get(reverse("home"))

    assert _missing(response, labels) == []


def test_edit_page_is_translated(french_client, dune):
    """The header of the edit page names the media, and the chips, typed ones included, name what they remove."""
    labels = [">Modifier Dune</h1>", 'aria-label="Supprimer Test Author"', 'aria-label="Supprimer {name}"']

    response = french_client.get(reverse("media_edit", args=[dune.pk]))

    assert _missing(response, labels) == []


def test_other_pages_are_translated(french_client, dune):
    """The covers of the statistics and the warning of the backup page are translated as whole sentences."""
    warning = (
        "L'importation d'une sauvegarde va <strong class=\"text-error\">SUPPRIMER TOUTES vos données actuelles</strong>"
        " et les remplacer par les données de la sauvegarde."
    )

    stats = french_client.get(reverse("stats"), {"year": 2024})
    backup = french_client.get(reverse("backup_manage"))

    assert _missing(stats, ['aria-label="Dune, Note : 7 sur 10"']) == []
    assert _missing(backup, [warning]) == []


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (lambda media: reverse("media_add"), "'Dune' créé avec succès"),
        (lambda media: reverse("media_edit", args=[media.pk]), "'Dune' mis à jour avec succès"),
    ],
    ids=["created", "updated"],
)
def test_saved_media_messages_are_translated(french_client, media, url, message):
    """The message confirming that a media was saved is translated."""
    response = french_client.post(url(media), media_form_data(title="Dune"))

    assert messages_of(response) == [message]


@pytest.mark.parametrize(
    ("url_name", "error"), [("agent_select_htmx", "Agent non trouvé"), ("tag_select_htmx", "Mot-clé non trouvé")]
)
def test_missing_chip_errors_are_translated(french_client, url_name, error):
    """Picking a contributor or a tag that no longer exists says so in French."""
    response = french_client.post(reverse(url_name), {"id": 0})

    assert response.context["error"] == error


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("tmdb", "Clé d'API TMDB non configurée"),
        ("igdb", "Identifiants de l'API IGDB non configurés"),
        ("musicbrainz", "La recherche a échoué"),
    ],
)
def test_import_search_errors_are_translated(french_client, api_responses, settings, source, error):
    """A source that is not configured, or that cannot be reached, is reported in French."""
    settings.TMDB_API_KEY = settings.TWITCH_CLIENT_ID = ""

    response = french_client.get(reverse("import_search_htmx"), {"source": source, "q": "dune"})

    assert response.context["error"] == error


def test_invalid_review_date_error_is_translated(db):
    """The error of django-partial-date, which ships no French translation, is translated by the app."""
    with translation.override("fr"):
        errors = list(MediaForm(data=media_form_data(review_date="2024-13")).errors["review_date"])

    assert errors == ["'2024-13' n'est pas une date valide (AAAA, AAAA-MM ou AAAA-MM-JJ)"]
