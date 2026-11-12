import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AIConversationTurn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.UUIDField(db_index=True, default=uuid.uuid4)),
                ("transcript", models.TextField()),
                ("draft_order", models.JSONField(default=dict)),
                ("validation", models.JSONField(default=dict)),
                ("signals", models.JSONField(default=dict)),
                ("action", models.CharField(choices=[("ASK", "Ask"), ("REPAIR", "Repair"), ("CONFIRM", "Confirm"), ("ESCALATE", "Escalate")], max_length=10)),
                ("policy", models.CharField(max_length=2)),
                ("latency_ms", models.FloatField(default=0)),
                ("token_usage", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ("created_at", "id")},
        ),
    ]
