from django.conf import settings
from django.db import models

from apps.menu.models import MenuItem
from apps.vendors.models import Vendor


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        ACCEPTED = "ACCEPTED", "Accepted"
        PREPARING = "PREPARING", "Preparing"
        READY = "READY", "Ready"
        DISPATCHED = "DISPATCHED", "Dispatched"
        DELIVERED = "DELIVERED", "Delivered"
        REJECTED = "REJECTED", "Rejected"
        FALLBACK = "FALLBACK", "Fallback"
        CANCELLED = "CANCELLED", "Cancelled"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="orders")
    student_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    delivery_location = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)
    vendor_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Order #{self.pk} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    customization = models.CharField(max_length=255, blank=True)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.menu_item.name} x {self.quantity}"
