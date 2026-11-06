import uuid

from django.db import models


class AIConversationTurn(models.Model):
    class Action(models.TextChoices):
        ASK = "ASK", "Ask"
        REPAIR = "REPAIR", "Repair"
        CONFIRM = "CONFIRM", "Confirm"
        ESCALATE = "ESCALATE", "Escalate"

    session_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    transcript = models.TextField()
    draft_order = models.JSONField(default=dict)
    validation = models.JSONField(default=dict)
    signals = models.JSONField(default=dict)
    action = models.CharField(max_length=10, choices=Action.choices)
    policy = models.CharField(max_length=2)
    latency_ms = models.FloatField(default=0)
    token_usage = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"{self.policy} {self.action} turn {self.pk}"
