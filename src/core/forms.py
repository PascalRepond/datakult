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
            "pub_year": forms.NumberInput(attrs={"class": "input validator", "placeholder": _("Release year")}),
            "review": forms.Textarea(attrs={"class": "textarea", "placeholder": _("Review")}),
            "review_date": forms.TextInput(attrs={"class": "input validator", "placeholder": _("Review date")}),
        }
