from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.http import require_POST

from .forms import MediaForm


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
def validate_media_field(request):
    """Validate a single MediaForm field via HTMX."""
    form = MediaForm(request.POST, request.FILES)
    field_name = request.POST.get("field_name")
    return _validate_field_htmx(form, field_name)
