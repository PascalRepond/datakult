from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import migrations
from django.db.models import Q
from PIL import Image

from core.models import compress_image, dominant_color

# Longest side of a compressed cover
COVER_MAX_SIDE = 800


def compress_covers(apps, _schema_editor):
    """Compress the covers kept as downloaded from external sources, leaving those already compressed untouched."""
    Media = apps.get_model("core", "Media")
    for media in Media.objects.exclude(Q(cover__isnull=True) | Q(cover="")):
        old_name = media.cover.name
        try:
            with Image.open(media.cover) as img:
                if img.format == "JPEG" and max(img.size) <= COVER_MAX_SIDE:
                    continue  # Compressing a JPEG again would degrade it for little space saved
            compressed = compress_image(media.cover)
        except OSError, ValidationError:
            continue  # Missing or unreadable file, left as it is
        finally:
            media.cover.close()
        media.cover_color = dominant_color(compressed)
        media.cover.save(Path(old_name).with_suffix(".jpg").name, compressed, save=False)
        media.cover.storage.delete(old_name)
        media.save(update_fields=["cover", "cover_color"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_media_cover_color"),
    ]

    operations = [
        migrations.RunPython(compress_covers, migrations.RunPython.noop),
    ]
