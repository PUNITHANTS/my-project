import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.conversational_ordering.models import AIConversationTurn


class Command(BaseCommand):
    help = "Export recorded AI turns as JSONL for analysis. Turn logging must be enabled first."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        output = Path(options["output"])
        if output.exists():
            raise CommandError(f"Refusing to overwrite existing log export: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as stream:
            for row in AIConversationTurn.objects.iterator(chunk_size=500):
                record = {
                    "turn_id": row.pk,
                    "session_id": str(row.session_id),
                    "transcript": row.transcript,
                    "draft_order": row.draft_order,
                    "validation": row.validation,
                    "features": row.signals,
                    "action": row.action,
                    "policy": row.policy,
                    "latency_ms": row.latency_ms,
                    "token_usage": row.token_usage,
                    "created_at": row.created_at.isoformat(),
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Exported turn logs to {output}"))
