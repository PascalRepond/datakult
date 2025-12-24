"""
Tests for accounts.forms module.
"""

from accounts.forms import CustomPasswordChangeForm, UserProfileForm


class TestUserProfileForm:
    """Tests for the UserProfileForm."""

    def test_form_has_expected_fields(self):
        """The form contains the expected fields."""
        form = UserProfileForm()

        assert "username" in form.fields
        assert "email" in form.fields
        assert "first_name" in form.fields
        assert "last_name" in form.fields
        # Password should NOT be in this form
        assert "password" not in form.fields

    def test_form_widgets_have_daisyui_classes(self):
        """Form widgets have the expected DaisyUI styling classes."""
        form = UserProfileForm()

        for field_name in form.fields:
            widget_class = form.fields[field_name].widget.attrs.get("class", "")
            assert "input" in widget_class
            assert "validator" in widget_class
            assert "w-full" in widget_class

    def test_form_widgets_have_htmx_validation_attrs(self):
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


class TestCustomPasswordChangeForm:
    """Tests for the CustomPasswordChangeForm."""

    def test_form_widgets_have_daisyui_classes(self, user):
        """Form widgets have the expected DaisyUI styling classes."""
        form = CustomPasswordChangeForm(user)

        for field_name in form.fields:
            widget_class = form.fields[field_name].widget.attrs.get("class", "")
            assert "input" in widget_class
            assert "validator" in widget_class
            assert "w-full" in widget_class

    def test_form_widgets_have_htmx_validation_attrs(self, user):
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
