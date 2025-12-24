from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse

User = get_user_model()


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information."""

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        validation_url = reverse("accounts:validate_profile_field")
        for field_name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": "input validator w-full",
                    "hx-post": validation_url,
                    "hx-trigger": "input changed delay:500ms",
                    "hx-target": f"#error-{field_name}",
                    "hx-include": f"[name='{field_name}']",
                    "hx-vals": f'{{"field_name": "{field_name}"}}',
                }
            )


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with Tailwind/DaisyUI styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        validation_url = reverse("accounts:validate_password_field")
        for field_name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": "input validator w-full",
                    "hx-post": validation_url,
                    "hx-trigger": "input changed delay:500ms",
                    "hx-target": f"#error-{field_name}",
                    "hx-include": "[name^='old_password'],[name^='new_password']",
                    "hx-vals": f'{{"field_name": "{field_name}"}}',
                }
            )
