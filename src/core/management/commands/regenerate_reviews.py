"""Regenerate rendered reviews command."""

from django.core.management.base import BaseCommand

from core.models import Media


class Command(BaseCommand):
    """Regenerate review_rendered field for all Media objects with reviews."""

    help = "Regenerate the review_rendered field for all Media objects that have a review"

    def handle(self, **options):  # noqa: ARG002
        """Execute the review regeneration."""
        self.stdout.write("Regenerating rendered reviews…")

        # Get all Media objects that have a non-empty review
        media_with_reviews = Media.objects.exclude(review="")
        total_count = media_with_reviews.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING("No media with reviews found."))
            return

        self.stdout.write(f"Found {total_count} media with reviews to process…")

        # Process each media object
        updated_count = 0
        for media in media_with_reviews:
            # Simply calling save() will trigger the MarkdownField
            # to regenerate the review_rendered field
            media.save()
            updated_count += 1

            # Show progress every 10 items
            if updated_count % 10 == 0:
                self.stdout.write(f"  Processed {updated_count}/{total_count}…")

        self.stdout.write(self.style.SUCCESS(f"✓ Successfully regenerated {updated_count} rendered reviews"))
