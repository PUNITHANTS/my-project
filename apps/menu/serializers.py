from rest_framework import serializers

from .models import MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
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
        )
