"""Validation of form fields while they are typed, through HTMX."""

from django.http import HttpResponse
from django.template.loader import render_to_string

FIELD_ERROR_TEMPLATE = "partials/common/field_error.html"


def field_error_response(form, field_name):
    """Validate a form, and return the first error of one of its fields rendered to show below it, if it has one."""
    form.is_valid()
    if field_name in form.fields and (errors := form.errors.get(field_name)):
        return HttpResponse(render_to_string(FIELD_ERROR_TEMPLATE, {"error": errors[0]}))
    return HttpResponse("")
