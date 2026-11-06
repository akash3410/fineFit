"""
Signal handlers for the catalog domain.

Keeps stored media in sync with database rows so deleting a ``ProductImage``
(or a ``Product``, which cascades to its images) never leaves orphaned files
on disk regardless of whether the deletion happened through the API, the
admin, or the shell.
"""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProductImage


@receiver(post_delete, sender=ProductImage)
def delete_product_image_file(sender, instance, **kwargs):
    """Remove the stored media file when a ``ProductImage`` row is deleted."""
    file_field = instance.image
    name = file_field.name if file_field and file_field.name else None
    if name:
        try:
            file_field.delete(save=False)
        except OSError:
            # A missing or unreadable file must not block transaction commit.
            pass
