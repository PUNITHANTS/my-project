from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        VENDOR = "vendor", "Vendor"
        ADMIN = "admin", "Admin"
        SUPERADMIN = "superadmin", "Super Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"
