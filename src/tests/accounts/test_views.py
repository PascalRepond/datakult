"""
Tests for accounts.views module.

These tests verify the behavior of the profile edit view.
Only tests custom functionality, not Django's built-in authentication.
"""

import pytest
from django.urls import reverse

from core.utils import get_datakult_version
from tests.helpers import messages_of


def test_profile_edit_shows_both_forms_prefilled(logged_in_client, user):
    """The profile page shows the password form, and the profile form filled with the user data."""
    response = logged_in_client.get(reverse("accounts:profile_edit"))

    assert response.context["profile_form"].initial["username"] == user.username
    assert response.context["profile_form"].initial["email"] == user.email
    assert 'name="old_password"' in response.content.decode()


def test_update_profile_success(logged_in_client, user):
    """Submitting valid profile data updates the user."""
    url = reverse("accounts:profile_edit")
    data = {
        "username": "newusername",
        "email": "newemail@example.com",
        "first_name": "New",
        "last_name": "Name",
        "update_profile": "",  # Indicates which form was submitted
    }

    response = logged_in_client.post(url, data)

    assert response.status_code == 302  # Redirect after success
    user.refresh_from_db()
    assert user.username == "newusername"
    assert user.email == "newemail@example.com"
    assert user.first_name == "New"
    assert user.last_name == "Name"


def test_change_password_replaces_the_old_one(logged_in_client, user):
    """A valid password change sets the new password, after which the old one no longer works."""
    url = reverse("accounts:profile_edit")
    data = {
        "old_password": "testpass123",
        "new_password1": "newSecurePass456!",
        "new_password2": "newSecurePass456!",
        "change_password": "",  # Indicates which form was submitted
    }

    response = logged_in_client.post(url, data)

    assert response.status_code == 302  # Redirect after success
    user.refresh_from_db()
    assert user.check_password("newSecurePass456!")

    response = logged_in_client.post(url, data)

    assert response.status_code == 200  # Form re-displayed with errors
    assert response.context["password_form"].errors


@pytest.mark.parametrize(
    ("url_name", "data", "expected"),
    [
        ("accounts:validate_profile_field", {"field_name": "username", "username": "testuser"}, ""),
        (
            "accounts:validate_profile_field",
            {"field_name": "email", "email": "not-an-email"},
            '<span class="label-text-alt text-error">Enter a valid email address.</span>',
        ),
        (
            "accounts:validate_password_field",
            {"field_name": "new_password2", "new_password1": "newSecurePass456!", "new_password2": "other"},
            '<span class="label-text-alt text-error">The two password fields didn\u2019t match.</span>',
        ),
        ("accounts:validate_password_field", {"field_name": "unknown"}, ""),
    ],
    ids=["valid", "invalid profile field", "invalid password field", "unknown field"],
)
def test_profile_fields_are_validated_one_at_a_time(logged_in_client, url_name, data, expected):
    """The validation endpoints of the profile page return the error of the typed field only, if it has one."""
    response = logged_in_client.post(reverse(url_name), data)

    assert response.content.decode().strip() == expected


@pytest.mark.parametrize(("language", "confirmed"), [("fr", True), ("invalid", False)])
def test_set_language_confirms_a_supported_language(logged_in_client, language, confirmed):
    """Picking a supported language is confirmed by a message, and an unsupported one is not."""
    response = logged_in_client.post(reverse("accounts:set_language"), {"language": language})

    assert ("Language preference updated." in messages_of(response)) is confirmed


def test_login_shows_short_error_on_wrong_credentials(client, user):
    """A failed login shows a short error instead of silently reloading the form."""
    response = client.post(reverse("login"), {"username": "testuser", "password": "wrong"})

    assert "Invalid credentials." in response.content.decode()


def test_login_fields_support_password_managers(client, db):
    """The login fields declare their autocomplete purpose."""
    content = client.get(reverse("login")).content.decode()

    assert 'autocomplete="username"' in content
    assert 'autocomplete="current-password"' in content


def test_login_page_declares_the_active_language(client, db):
    """The html lang attribute of the login page follows the language of the request."""
    response = client.get(reverse("login"), HTTP_ACCEPT_LANGUAGE="fr")

    assert '<html lang="fr">' in response.content.decode()


def test_profile_shows_version_and_credits(logged_in_client):
    """The profile page tells the app version and credits the logo."""
    content = logged_in_client.get(reverse("accounts:profile_edit")).content.decode()

    assert f"v{get_datakult_version()}" in content
    assert "Freepik" in content
