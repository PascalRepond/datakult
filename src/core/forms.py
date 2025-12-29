from django import forms
from django.urls import reverse
from django.utils.translation import gettext as _
from markdownfield.widgets import MDEWidget

from .models import Media


class CoverImageWidget(forms.ClearableFileInput):
    """Custom widget for cover image with preview and clear functionality."""

    template_name = "widgets/cover_input.html"


class StarRatingWidget(forms.Widget):
    """Custom widget for star rating input (1-10 scale)."""

    template_name = "widgets/star_rating.html"

    def get_context(self, name, value, attrs):
        """
        Add score choices with their verbose names to the template context.

        This allows the template to display the descriptive labels
        (e.g., "Adored", "Loved") when hovering over stars.
        """
        context = super().get_context(name, value, attrs)
        # Get the choices from the Media model's score field
        score_field = Media._meta.get_field("score")  # noqa: SLF001
        context["score_choices"] = score_field.choices
        return context


class MediaForm(forms.ModelForm):
    """Form for creating and editing Media objects with dynamic HTMX validation."""

    class Meta:
        model = Media
        fields = (
            "title",
            "contributors",
            "media_type",
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
            "status": forms.Select(attrs={"class": "select validator w-full"}),
            "pub_year": forms.NumberInput(attrs={"class": "input validator w-full", "placeholder": _("YYYY")}),
            "score": StarRatingWidget(attrs={"class": "validator"}),
            "review": MDEWidget(),
            "review_date": forms.TextInput(
                attrs={
                    "class": "input validator w-full",
                    "placeholder": _("YYYY, MM-YYYY, or DD-MM-YYYY"),
                }
            ),
            "cover": CoverImageWidget(attrs={"class": "file-input file-input-ghost w-full max-w-xs"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the form and add HTMX attributes for dynamic field validation.

        Configures all form fields (except cover and contributors) with HTMX
        attributes to enable real-time validation on user input.
        """
        super().__init__(*args, **kwargs)
        # Add HTMX attributes for dynamic validation
        validation_url = reverse("media_validate_field")
        for field_name, field in self.fields.items():
            # Do not add dynamic validation on file or M2M fields (cover, contributors)
            if field_name in ["cover", "contributors"]:
                continue
            field.widget.attrs.update(
                {
                    "hx-post": validation_url,
                    "hx-trigger": "input changed delay:500ms",
                    "hx-target": f"#error-{field_name}",
                    "hx-include": f"[name='{field_name}']",
                    "hx-vals": f'{{"field_name": "{field_name}"}}',
                }
            )
