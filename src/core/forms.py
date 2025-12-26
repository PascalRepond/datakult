from django import forms
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import Media


class MediaForm(forms.ModelForm):
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
            "title": forms.TextInput(attrs={"class": "input validator w-full", "placeholder": _("Title")}),
            "media_type": forms.Select(attrs={"class": "select validator w-full"}),
            "status": forms.Select(attrs={"class": "select validator w-full"}),
            "pub_year": forms.NumberInput(attrs={"class": "input validator w-full", "placeholder": _("Release year")}),
            "score": forms.Select(attrs={"class": "select validator w-full"}),
            "review": forms.Textarea(attrs={"class": "textarea validator w-full", "placeholder": _("Review")}),
            "review_date": forms.TextInput(attrs={"class": "input validator w-full", "placeholder": _("Review date")}),
            "cover": forms.FileInput(attrs={"class": "file-input validator w-full"}),
        }

    def __init__(self, *args, **kwargs):
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
