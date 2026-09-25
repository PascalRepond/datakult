from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils.translation import gettext_lazy as _

from core.forms import HtmxValidationMixin

User = get_user_model()
FIELD_CLASS = "input validator w-full"


class UserProfileForm(HtmxValidationMixin, forms.ModelForm):
    """Form for updating user profile information."""

    validation_url_name = "accounts:validate_profile_field"
    validated_field_class = FIELD_CLASS

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]


class LoginForm(AuthenticationForm):
    """Login form with a short error message on invalid credentials."""

    error_messages = {**AuthenticationForm.error_messages, "invalid_login": _("Invalid credentials.")}


class CustomPasswordChangeForm(HtmxValidationMixin, PasswordChangeForm):
    """Custom password change form with Tailwind/DaisyUI styling."""

    validation_url_name = "accounts:validate_password_field"
    validated_field_class = FIELD_CLASS
