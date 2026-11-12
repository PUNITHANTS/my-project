from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.conversational_ordering.models import AIConversationTurn


class Command(BaseCommand):
    help = "Delete AI turn logs older than a retention period. Requires explicit --confirm."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-days", type=int, required=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        days = options["older_than_days"]
        if days < 1:
            raise CommandError("--older-than-days must be at least 1.")
        cutoff = timezone.now() - timedelta(days=days)
        rows = AIConversationTurn.objects.filter(created_at__lt=cutoff)
        count = rows.count()
        if not options["confirm"]:
            self.stdout.write(f"{count} AI turn log(s) are older than {days} days. No records deleted; rerun with --confirm to delete.")
            return
        rows.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} AI turn log(s)."))
