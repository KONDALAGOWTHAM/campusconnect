from django.core.management.base import BaseCommand
from django.utils import timezone

from market.models import RateBucket


class Command(BaseCommand):
    help = "Delete expired request rate-limit buckets."

    def handle(self, *args, **options):
        deleted, _ = RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f"Deleted {deleted} expired buckets.")
