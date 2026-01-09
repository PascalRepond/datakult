from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.views.i18n import set_language as django_set_language

from .forms import CustomPasswordChangeForm, UserProfileForm


@login_required
def profile_edit(request):
    """View for editing user profile and changing password."""
    profile_form = UserProfileForm(instance=request.user)
    password_form = CustomPasswordChangeForm(request.user)

    if request.method == "POST":
        # Check which form was submitted
        if "update_profile" in request.POST:
            profile_form = UserProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, _("Profile updated."))
                return redirect("accounts:profile_edit")
        elif "change_password" in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                # Keep the user logged in after password change
                update_session_auth_hash(request, user)
                messages.success(request, _("Password changed."))
                return redirect("accounts:profile_edit")

    # Get current language and available languages
    current_language = translation.get_language()

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "profile_form": profile_form,
            "password_form": password_form,
            "languages": settings.LANGUAGES,
            "current_language": current_language,
        },
    )


def _validate_field_htmx(form, field_name):
    """Helper to validate a single form field and return HTMX response."""
    form.is_valid()  # Trigger validation

    if field_name and field_name in form.fields:
        errors = form.errors.get(field_name, [])
        if errors:
            return HttpResponse(f'<span class="label-text-alt text-error">{escape(errors[0])}</span>')
    return HttpResponse("")


@require_POST
@login_required
def validate_profile_field(request):
    """Validate a single profile form field via HTMX."""
    form = UserProfileForm(request.POST, instance=request.user)
    field_name = request.POST.get("field_name")
    return _validate_field_htmx(form, field_name)


@require_POST
@login_required
def validate_password_field(request):
    """Validate a single password form field via HTMX."""
    form = CustomPasswordChangeForm(request.user, request.POST)
    field_name = request.POST.get("field_name")
    return _validate_field_htmx(form, field_name)


@require_POST
@login_required
@csrf_protect
def set_language_view(request):
    """Custom wrapper to set language with a success message."""
    response = django_set_language(request)

    # Add success message after language is set
    language = request.POST.get("language")
    if language and language in dict(settings.LANGUAGES):
        messages.success(request, _("Language preference updated."))

    return response
