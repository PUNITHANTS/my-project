from django.conf import settings
from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=255)
    location_label = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    intake_paused = models.BooleanField(default=False)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_vendors",
    )

    def __str__(self) -> str:
        return self.name
