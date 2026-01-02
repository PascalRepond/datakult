"""
Tests for accounts.views module.

These tests verify the behavior of the profile edit view.
Only tests custom functionality, not Django's built-in authentication.
"""

from django.urls import reverse


class TestProfileEditView:
    """Tests for the profile_edit view."""

    def test_profile_edit_accessible_when_logged_in(self, logged_in_client):
        """The profile edit view is accessible when logged in."""
        response = logged_in_client.get(reverse("accounts:profile_edit"))

        assert response.status_code == 200

    def test_profile_edit_displays_both_forms(self, logged_in_client):
        """The view displays both profile and password forms."""
        response = logged_in_client.get(reverse("accounts:profile_edit"))

        assert response.status_code == 200
        assert "profile_form" in response.context
        assert "password_form" in response.context

    def test_profile_edit_prefills_user_data(self, logged_in_client, user):
        """The profile form is prefilled with current user data."""
        response = logged_in_client.get(reverse("accounts:profile_edit"))

        assert response.context["profile_form"].initial["username"] == user.username
        assert response.context["profile_form"].initial["email"] == user.email

    def test_update_profile_success(self, logged_in_client, user):
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

    def test_update_profile_invalid_username(self, logged_in_client, user, django_user_model):
        """Submitting a duplicate username shows an error."""
        # Create another user with the username we'll try to use
        django_user_model.objects.create_user(
            username="existinguser",
            password="pass123",
        )

        url = reverse("accounts:profile_edit")
        data = {
            "username": "existinguser",
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "update_profile": "",
        }

        response = logged_in_client.post(url, data)

        assert response.status_code == 200  # Form re-displayed with errors
        assert response.context["profile_form"].errors

    def test_change_password_success(self, logged_in_client, user):
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

    def test_change_password_wrong_old_password(self, logged_in_client):
        """Submitting wrong old password shows an error."""
        url = reverse("accounts:profile_edit")
        data = {
            "old_password": "wrongpassword",
            "new_password1": "newSecurePass456!",
            "new_password2": "newSecurePass456!",
            "change_password": "",
        }

        response = logged_in_client.post(url, data)

        assert response.status_code == 200  # Form re-displayed with errors
        assert response.context["password_form"].errors

    def test_user_stays_logged_in_after_password_change(self, logged_in_client):
        """User remains logged in after changing password."""
        url = reverse("accounts:profile_edit")
        data = {
            "old_password": "testpass123",
            "new_password1": "newSecurePass456!",
            "new_password2": "newSecurePass456!",
            "change_password": "",
        }

        logged_in_client.post(url, data)

        # Check user is still authenticated by accessing a protected page
        response = logged_in_client.get(reverse("accounts:profile_edit"))
        assert response.status_code == 200
