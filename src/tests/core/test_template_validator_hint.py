import pytest
from django.template import Context, Template

from core.forms import MediaForm


@pytest.mark.django_db
def test_media_edit_template_shows_validator_hint():
    form = MediaForm(data={"title": "", "media_type": "BOOK", "status": "PLANNED"})
    form.is_valid()
    template = Template("""
    {% if form.title.errors %}<span class="validator-hint">{{ form.title.errors.0 }}</span>{% endif %}
    """)
    rendered = template.render(Context({"form": form}))
    assert "validator-hint" in rendered
    assert form.errors["title"]
