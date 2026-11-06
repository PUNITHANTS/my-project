from rest_framework import serializers
from django.db import transaction

from .models import MenuAvailabilityWindow, MenuItem, MenuOption, MenuOptionGroup


class MenuOptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MenuOption
        fields = ("id", "name", "is_available", "sort_order")

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Option names cannot be blank.")
        return value.strip()


class MenuOptionGroupSerializer(serializers.ModelSerializer):
    options = MenuOptionSerializer(many=True, read_only=True)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MenuOptionGroup
        fields = (
            "id",
            "name",
            "is_required",
            "min_selections",
            "max_selections",
            "sort_order",
            "options",
        )


class MenuAvailabilityWindowSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    weekday_name = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = MenuAvailabilityWindow
        fields = ("id", "weekday", "weekday_name", "start_time", "end_time", "is_active")

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError("Availability end time must be after start time.")
        return attrs


class MenuOptionInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    is_available = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(min_value=0, max_value=65535, required=False, default=0)

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Option names cannot be blank.")
        return value


class MenuOptionGroupInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    is_required = serializers.BooleanField(required=False, default=False)
    min_selections = serializers.IntegerField(min_value=0, max_value=65535, required=False, default=0)
    max_selections = serializers.IntegerField(min_value=1, max_value=65535, required=False, default=1)
    sort_order = serializers.IntegerField(min_value=0, max_value=65535, required=False, default=0)
    options = MenuOptionInputSerializer(many=True, required=False, default=list)

    def validate(self, attrs):
        if attrs["min_selections"] > attrs["max_selections"]:
            raise serializers.ValidationError("min_selections cannot exceed max_selections.")
        options = attrs["options"]
        if not options:
            raise serializers.ValidationError("Each option group must contain at least one option.")
        names = [option["name"].casefold() for option in options]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Option names must be unique within a group.")
        if attrs["max_selections"] > len(options) and options:
            raise serializers.ValidationError("max_selections cannot exceed the number of options.")
        minimum = max(1 if attrs["is_required"] else 0, attrs["min_selections"])
        if minimum > len(options):
            raise serializers.ValidationError("The group requires more choices than it offers.")
        return attrs


class MenuItemSerializer(serializers.ModelSerializer):
    option_groups = MenuOptionGroupInputSerializer(many=True, required=False)
    availability_windows = MenuAvailabilityWindowSerializer(many=True, required=False)

    class Meta:
        model = MenuItem
        fields = (
            "id",
            "vendor",
            "name",
            "description",
            "price",
            "is_available",
            "prep_time_minutes",
            "max_quantity",
            "option_groups",
            "availability_windows",
        )

    def validate(self, attrs):
        groups = attrs.get("option_groups")
        if groups is not None:
            option_names = set()
            for group in groups:
                for option in group["options"]:
                    normalized = option["name"].strip().casefold()
                    if normalized in option_names:
                        raise serializers.ValidationError(
                            {"option_groups": "Option names must be unique across a menu item."}
                        )
                    option_names.add(normalized)

        windows = attrs.get("availability_windows")
        if windows is not None:
            by_day = {}
            for window in sorted(windows, key=lambda row: (row["weekday"], row["start_time"])):
                previous_end = by_day.get(window["weekday"])
                if previous_end and window["start_time"] < previous_end:
                    raise serializers.ValidationError(
                        {"availability_windows": "Availability windows for a day cannot overlap."}
                    )
                by_day[window["weekday"]] = window["end_time"]
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["option_groups"] = MenuOptionGroupSerializer(
            instance.option_groups.all(), many=True
        ).data
        data["availability_windows"] = MenuAvailabilityWindowSerializer(
            instance.availability_windows.all(), many=True
        ).data
        return data

    @transaction.atomic
    def create(self, validated_data):
        option_groups = validated_data.pop("option_groups", [])
        availability_windows = validated_data.pop("availability_windows", [])
        item = MenuItem.objects.create(**validated_data)
        self._replace_option_groups(item, option_groups)
        self._replace_availability_windows(item, availability_windows)
        return item

    @transaction.atomic
    def update(self, instance, validated_data):
        option_groups = validated_data.pop("option_groups", serializers.empty)
        availability_windows = validated_data.pop(
            "availability_windows", serializers.empty
        )
        instance = super().update(instance, validated_data)
        if option_groups is not serializers.empty:
            self._replace_option_groups(instance, option_groups)
        if availability_windows is not serializers.empty:
            self._replace_availability_windows(instance, availability_windows)
        return instance

    @staticmethod
    def _replace_option_groups(item, groups):
        item.option_groups.all().delete()
        for group_data in groups:
            options = group_data.pop("options", [])
            group = MenuOptionGroup.objects.create(menu_item=item, **group_data)
            MenuOption.objects.bulk_create(
                [MenuOption(option_group=group, **option) for option in options]
            )

    @staticmethod
    def _replace_availability_windows(item, windows):
        item.availability_windows.all().delete()
        MenuAvailabilityWindow.objects.bulk_create(
            [MenuAvailabilityWindow(menu_item=item, **window) for window in windows]
        )
