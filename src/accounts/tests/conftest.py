"""
Fixtures for accounts app tests.
"""

import pytest


@pytest.fixture
def user(db, django_user_model):
    """Create and return a test user."""
    return django_user_model.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def logged_in_client(client, user):
    """Return a client with an authenticated user."""
    client.force_login(user)
    return client
