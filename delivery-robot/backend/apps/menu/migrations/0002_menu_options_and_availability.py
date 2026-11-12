import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("menu", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="max_quantity",
            field=models.PositiveIntegerField(default=10),
        ),
        migrations.CreateModel(
            name="MenuOptionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("is_required", models.BooleanField(default=False)),
                ("min_selections", models.PositiveSmallIntegerField(default=0)),
                ("max_selections", models.PositiveSmallIntegerField(default=1)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="option_groups", to="menu.menuitem")),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="MenuOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("is_available", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("option_group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="menu.menuoptiongroup")),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="MenuAvailabilityWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.PositiveSmallIntegerField(choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")])),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="availability_windows", to="menu.menuitem")),
            ],
            options={"ordering": ("weekday", "start_time")},
        ),
        migrations.AddConstraint(
            model_name="menuoptiongroup",
            constraint=models.CheckConstraint(condition=models.Q(("max_selections__gte", 1), ("min_selections__lte", models.F("max_selections"))), name="menu_option_group_selection_bounds"),
        ),
        migrations.AddConstraint(
            model_name="menuoption",
            constraint=models.UniqueConstraint(fields=("option_group", "name"), name="unique_menu_option_name"),
        ),
        migrations.AddConstraint(
            model_name="menuavailabilitywindow",
            constraint=models.CheckConstraint(condition=models.Q(("end_time__gt", models.F("start_time"))), name="menu_window_end_after_start"),
        ),
    ]
