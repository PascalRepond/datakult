from django import forms
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
            "media_type": forms.Select(attrs={"class": "select w-full"}),
            "status": forms.Select(attrs={"class": "select w-full"}),
            "pub_year": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "placeholder": _("Release year")}
            ),
            "score": forms.Select(attrs={"class": "select w-full"}),
            "review": forms.Textarea(attrs={"class": "textarea w-full", "placeholder": _("Review")}),
            "review_date": forms.TextInput(attrs={"class": "input validator w-full", "placeholder": _("Review date")}),
            "cover": forms.FileInput(attrs={"class": "file-input w-full"}),
        }
