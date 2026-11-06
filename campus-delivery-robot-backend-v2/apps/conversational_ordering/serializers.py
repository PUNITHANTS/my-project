from rest_framework import serializers


class ParseOrderTurnSerializer(serializers.Serializer):
    transcript = serializers.CharField(max_length=2000, trim_whitespace=True)
    session_id = serializers.UUIDField()
