import pytest

from core.forms import MediaForm


@pytest.mark.django_db
def test_mediaform_htmx_attrs():
    form = MediaForm()
    for field_name, field in form.fields.items():
        widget = field.widget
        if field_name in ["cover", "contributors", "tags"]:
            # These fields should not have HTMX attributes
            for attr in ["hx-post", "hx-trigger", "hx-target", "hx-include", "hx-vals"]:
                assert attr not in widget.attrs
        else:
            assert widget.attrs.get("hx-post"), f"hx-post missing on {field_name}"
            assert widget.attrs.get("hx-trigger"), f"hx-trigger missing on {field_name}"
            assert widget.attrs.get("hx-target"), f"hx-target missing on {field_name}"
            assert widget.attrs.get("hx-include"), f"hx-include missing on {field_name}"
            assert widget.attrs.get("hx-vals"), f"hx-vals missing on {field_name}"
