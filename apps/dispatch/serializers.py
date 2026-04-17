from rest_framework import serializers

from .models import RobotDispatch


class RobotDispatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = RobotDispatch
        fields = ("id", "order", "provider", "status", "request_payload", "response_payload", "created_at", "updated_at")
