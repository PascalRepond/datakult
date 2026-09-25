import json

from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from markdownfield.widgets import MDEWidget

from .models import Media, Score

# Fields are validated once their typing pauses
VALIDATION_TRIGGER = "input changed delay:500ms"


class HtmxValidationMixin:
    """
    Validate fields while they are typed, each showing its error in its #error-<field name> element.

    A form names its validation endpoint, and the fields to validate if not all of them, to which it may give a class.
    """

    validation_url_name: str
    validated_fields: tuple[str, ...] | None = None
    validated_field_class = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        validation_url = reverse(self.validation_url_name)
        for field_name in self.validated_fields or self.fields:
            attrs = self.fields[field_name].widget.attrs
            if self.validated_field_class:
                attrs["class"] = self.validated_field_class
            attrs.update(
                {
                    # htmx sends the whole form of a field with a POST, so that fields can be checked against others
                    "hx-post": validation_url,
                    "hx-trigger": VALIDATION_TRIGGER,
                    "hx-target": f"#error-{field_name}",
                    "hx-vals": json.dumps({"field_name": field_name}),
                }
            )


class CoverImageWidget(forms.ClearableFileInput):
    """Custom widget for cover image with preview and clear functionality."""

    template_name = "widgets/cover_input.html"

    class Media:
        js = ("js/cover_input.js",)


class ScorePickerWidget(forms.Widget):
    """Dropdown of every score, shown with its ring and verdict, and of an unrated choice."""

    template_name = "widgets/score_picker.html"

    def get_context(self, name, value, attrs):
        """
        Add score choices with their verbose names to the template context.

        This allows the template to display the score ring and verdict (e.g., "Adored", "Loved") of each score.
        """
        context = super().get_context(name, value, attrs)
        context["score_choices"] = Score.choices
        return context


class MediaForm(HtmxValidationMixin, forms.ModelForm):
    """
    Form for creating and editing Media objects with dynamic HTMX validation.

    Only the free-text fields, whose input can actually be invalid, are validated while typed: title (required),
    external_uri (URL format), pub_year (min/max range), and review_date (date format).
    """

    validation_url_name = "media_validate_field"
    validated_fields = ("title", "external_uri", "pub_year", "review_date")

    class Meta:
        model = Media
        fields = (
            "title",
            "contributors",
            "tags",
            "media_type",
            "external_uri",
            "status",
            "pub_year",
            "score",
            "review",
            "review_date",
            "cover",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "input validator w-full"}),
            "media_type": forms.Select(attrs={"class": "select validator w-full"}),
            "external_uri": forms.URLInput(attrs={"class": "input validator w-full"}),
            "status": forms.Select(attrs={"class": "select validator w-full"}),
            "pub_year": forms.NumberInput(attrs={"class": "input validator w-full", "placeholder": _("YYYY")}),
            "score": ScorePickerWidget(),
            "review": MDEWidget(options={"nativeSpellcheck": True, "inputStyle": "contenteditable"}),
            "review_date": forms.TextInput(
                attrs={
                    "class": "input validator w-full",
                    "placeholder": _("YYYY, YYYY-MM, or YYYY-MM-DD"),
                }
            ),
            "cover": CoverImageWidget(attrs={"class": "file-input file-input-ghost w-full max-w-xs"}),
        }
