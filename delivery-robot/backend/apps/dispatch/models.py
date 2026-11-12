from django.db import models

from apps.orders.models import Order


class RobotDispatch(models.Model):
    class Provider(models.TextChoices):
        ROBOT = "robot", "Robot"
        FALLBACK = "fallback", "Fallback"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="dispatch")
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.ROBOT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Dispatch #{self.pk} for Order #{self.order_id}"
