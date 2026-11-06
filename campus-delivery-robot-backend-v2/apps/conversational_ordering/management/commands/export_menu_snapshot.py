import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.conversational_ordering.menu_validation import load_menu_catalog


class Command(BaseCommand):
    help = "Export a timestamped menu snapshot for reproducible dialogue annotation and evaluation."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="Destination JSON path")

    def handle(self, *args, **options):
        output = Path(options["output"])
        if output.exists():
            raise CommandError(f"Refusing to overwrite existing snapshot: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": load_menu_catalog(),
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(payload['items'])} menu items to {output}"))
