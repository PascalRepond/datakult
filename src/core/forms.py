from django import forms
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import Media


class CoverImageWidget(forms.ClearableFileInput):
    """Custom widget for cover image with preview and clear functionality."""

    template_name = "widgets/cover_input.html"


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
            "score": forms.Select(attrs={"class": "select validator w-full"}),
            "review": forms.Textarea(attrs={"class": "textarea validator w-full"}),
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
