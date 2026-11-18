import logging
from contextlib import contextmanager

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProductImage, User

logger = logging.getLogger(__name__)


@contextmanager
def media_transaction():
    uploaded = []
    try:
        with transaction.atomic():
            yield uploaded
    except Exception:
        for file in uploaded:
            try:
                file.storage.delete(file.name)
            except Exception:
                logger.exception("Could not remove an upload after its database transaction failed")
        raise


def save_upload(field, upload, uploaded):
    field.save(upload.name, upload, save=False)
    uploaded.append(field)


def delete_after_commit(file):
    if file and file.name:
        transaction.on_commit(lambda: file.storage.delete(file.name), robust=True)


@receiver(post_delete, sender=ProductImage)
def remove_product_photo(sender, instance, **kwargs):
    delete_after_commit(instance.file)


@receiver(post_delete, sender=User)
def remove_profile_photo(sender, instance, **kwargs):
    delete_after_commit(instance.photo)
