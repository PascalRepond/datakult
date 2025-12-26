import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_htmx_validate_field_invalid(logged_in_client):
    url = reverse("media_validate_field")
    data = {"title": "", "field_name": "title"}
    response = logged_in_client.post(url, data, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert "validator-hint" in response.content.decode() or "text-error" in response.content.decode()


@pytest.mark.django_db
def test_htmx_validate_field_valid(logged_in_client):
    url = reverse("media_validate_field")
    data = {"title": "Valid Title", "field_name": "title"}
    response = logged_in_client.post(url, data, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response.content.decode().strip() == ""


@pytest.mark.django_db
def test_htmx_validate_field_no_validation_for_cover_contributors(logged_in_client):
    url = reverse("media_validate_field")
    # cover and contributors should not trigger validation markup
    data = {"field_name": "cover"}
    response = logged_in_client.post(url, data, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response.content.decode().strip() == ""
    data = {"field_name": "contributors"}
    response = logged_in_client.post(url, data, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response.content.decode().strip() == ""
