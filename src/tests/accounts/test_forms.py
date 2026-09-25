"""
Tests for accounts.forms module.
"""

import json

import pytest
from django.urls import reverse

from accounts.forms import CustomPasswordChangeForm, UserProfileForm


@pytest.mark.parametrize(
    ("make_form", "url_name"),
    [
        pytest.param(lambda user: UserProfileForm(instance=user), "accounts:validate_profile_field", id="profile"),
        pytest.param(CustomPasswordChangeForm, "accounts:validate_password_field", id="password"),
    ],
)
def test_every_field_is_validated_as_it_is_typed(user, make_form, url_name):
    """Every field of the profile forms is validated by the endpoint of its form, its error shown below it."""
    form = make_form(user)

    for field_name, field in form.fields.items():
        attrs = field.widget.attrs
        assert attrs["hx-post"] == reverse(url_name)
        assert attrs["hx-trigger"] == "input changed delay:500ms"
        assert attrs["hx-target"] == f"#error-{field_name}"
        assert json.loads(attrs["hx-vals"]) == {"field_name": field_name}
