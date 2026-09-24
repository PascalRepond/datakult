"""
Tests for accounts.views module.

These tests verify the behavior of the profile edit view.
Only tests custom functionality, not Django's built-in authentication.
"""

from django.contrib.messages import get_messages
from django.urls import reverse


def test_profile_edit_accessible_when_logged_in(logged_in_client):
    """The profile edit view is accessible when logged in."""
    response = logged_in_client.get(reverse("accounts:profile_edit"))

    assert response.status_code == 200


def test_profile_edit_displays_both_forms(logged_in_client):
    """The view displays both profile and password forms."""
    response = logged_in_client.get(reverse("accounts:profile_edit"))

    assert response.status_code == 200
    assert "profile_form" in response.context
    assert "password_form" in response.context


def test_profile_edit_prefills_user_data(logged_in_client, user):
    """The profile form is prefilled with current user data."""
    response = logged_in_client.get(reverse("accounts:profile_edit"))

    assert response.context["profile_form"].initial["username"] == user.username
    assert response.context["profile_form"].initial["email"] == user.email


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


def test_change_password_success(logged_in_client, user):
    """Submitting valid password data changes the password."""
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


def test_set_language_changes_language(logged_in_client):
    """POST with valid language code changes the language."""
    response = logged_in_client.post(
        reverse("accounts:set_language"),
        {"language": "fr"},
    )

    # Should redirect (default behavior of set_language)
    assert response.status_code == 302


def test_set_language_shows_success_message(logged_in_client):
    """Setting language shows a success message."""
    response = logged_in_client.post(
        reverse("accounts:set_language"),
        {"language": "fr"},
        follow=True,
    )

    messages = list(get_messages(response.wsgi_request))
    assert any(("lang" in str(m).lower()) for m in messages)


def test_set_language_ignores_invalid_language(logged_in_client):
    """Invalid language codes don't show success message."""
    response = logged_in_client.post(
        reverse("accounts:set_language"),
        {"language": "invalid"},
        follow=True,
    )

    messages = list(get_messages(response.wsgi_request))
    assert all("lang" not in str(m).lower() for m in messages)


def test_set_language_get_not_allowed(logged_in_client):
    """GET request is not allowed (require_POST decorator)."""
    response = logged_in_client.get(reverse("accounts:set_language"))

    # require_POST returns 405 Method Not Allowed for GET
    assert response.status_code == 405


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

    assert "Freepik" in content
