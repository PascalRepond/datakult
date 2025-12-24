"""
Root conftest.py for pytest configuration.

This file contains fixtures and configuration shared across all test modules.
"""

import pytest


@pytest.fixture
def api_client():
    """Provide a Django test client."""
    from django.test import Client

    return Client()
