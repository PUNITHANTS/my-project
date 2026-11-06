from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.vendors.models import Vendor


class MenuItem(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    prep_time_minutes = models.PositiveIntegerField(default=10)
    max_quantity = models.PositiveIntegerField(default=10)

    def __str__(self) -> str:
        return f"{self.vendor.name} - {self.name}"


class MenuOptionGroup(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="option_groups"
    )
    name = models.CharField(max_length=120)
    is_required = models.BooleanField(default=False)
    min_selections = models.PositiveSmallIntegerField(default=0)
    max_selections = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(max_selections__gte=1)
                & Q(min_selections__lte=models.F("max_selections")),
                name="menu_option_group_selection_bounds",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.menu_item.name}: {self.name}"


class MenuOption(models.Model):
    option_group = models.ForeignKey(
        MenuOptionGroup, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=120)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("option_group", "name"), name="unique_menu_option_name"
            ),
        ]

    def clean(self):
        if not self.option_group_id or not self.name:
            return
        duplicate = MenuOption.objects.filter(
            option_group__menu_item_id=self.option_group.menu_item_id,
            name__iexact=self.name.strip(),
        ).exclude(pk=self.pk)
        if duplicate.exists():
            raise ValidationError(
                {"name": "Option names must be unique across all groups for a menu item."}
            )

    def __str__(self) -> str:
        return self.name


class MenuAvailabilityWindow(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="availability_windows"
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("weekday", "start_time")
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="menu_window_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.menu_item.name} ({self.get_weekday_display()})"
