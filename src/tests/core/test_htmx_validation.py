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
def test_htmx_validate_field_blank_allowed_fields(logged_in_client):
    url = reverse("media_validate_field")
    # Fields with blank=True return no error when submitted empty
    for field_name in ["cover", "contributors", "review", "score"]:
        data = {"field_name": field_name}
        response = logged_in_client.post(url, data, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.content.decode().strip() == "", f"Expected no error for {field_name}"
