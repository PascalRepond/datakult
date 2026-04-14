"""
Tests for accounts.forms module.
"""

from accounts.forms import CustomPasswordChangeForm, UserProfileForm


def test_user_profile_form_has_expected_fields():
    """The form contains the expected fields."""
    form = UserProfileForm()

    assert "username" in form.fields
    assert "email" in form.fields
    assert "first_name" in form.fields
    assert "last_name" in form.fields
    # Password should NOT be in this form
    assert "password" not in form.fields


def test_user_profile_form_widgets_have_daisyui_classes():
    """Form widgets have the expected DaisyUI styling classes."""
    form = UserProfileForm()

    for field_name in form.fields:
        widget_class = form.fields[field_name].widget.attrs.get("class", "")
        assert "input" in widget_class
        assert "validator" in widget_class
        assert "w-full" in widget_class


def test_user_profile_form_widgets_have_htmx_validation_attrs():
    """Form widgets have the expected HTMX validation attributes."""
    form = UserProfileForm()

    for field_name in form.fields:
        widget_attrs = form.fields[field_name].widget.attrs
        assert "hx-post" in widget_attrs
        assert "hx-trigger" in widget_attrs
        assert widget_attrs["hx-trigger"] == "input changed delay:500ms"
        assert widget_attrs["hx-target"] == f"#error-{field_name}"
        assert widget_attrs["hx-include"] == f"[name='{field_name}']"
        assert "hx-vals" in widget_attrs


def test_password_change_form_widgets_have_daisyui_classes(user):
    """Form widgets have the expected DaisyUI styling classes."""
    form = CustomPasswordChangeForm(user)

    for field_name in form.fields:
        widget_class = form.fields[field_name].widget.attrs.get("class", "")
        assert "input" in widget_class
        assert "validator" in widget_class
        assert "w-full" in widget_class


def test_password_change_form_widgets_have_htmx_validation_attrs(user):
    """Form widgets have the expected HTMX validation attributes."""
    form = CustomPasswordChangeForm(user)

    for field_name in form.fields:
        widget_attrs = form.fields[field_name].widget.attrs
        assert "hx-post" in widget_attrs
        assert "hx-trigger" in widget_attrs
        assert widget_attrs["hx-trigger"] == "input changed delay:500ms"
        assert widget_attrs["hx-target"] == f"#error-{field_name}"
        assert "hx-include" in widget_attrs
        assert "hx-vals" in widget_attrs
