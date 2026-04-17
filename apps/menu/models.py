from django.db import models

from apps.vendors.models import Vendor


class MenuItem(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    prep_time_minutes = models.PositiveIntegerField(default=10)

    def __str__(self) -> str:
        return f"{self.vendor.name} - {self.name}"
