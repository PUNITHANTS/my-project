from rest_framework import serializers


class SelectedOptionSerializer(serializers.Serializer):
    """A tapped option, echoed back exactly as the previous turn offered it."""

    slot = serializers.CharField(max_length=40)
    menuItemId = serializers.CharField(max_length=40, required=False)
    value = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        if ("menuItemId" in attrs) == ("value" in attrs):
            raise serializers.ValidationError(
                "Send exactly one of menuItemId or value with a selected option."
            )
        return attrs


class CartEditSerializer(serializers.Serializer):
    """A touch edit on the cart card; quantity 0 removes the line."""

    line = serializers.IntegerField(min_value=0)
    quantity = serializers.IntegerField(min_value=0, max_value=1000)


class ParseOrderTurnSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    transcript = serializers.CharField(
        max_length=2000, trim_whitespace=True, required=False, allow_null=True
    )
    selected_option = SelectedOptionSerializer(required=False, allow_null=True)
    cart_edit = CartEditSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        inputs = [
            name
            for name in ("transcript", "selected_option", "cart_edit")
            if attrs.get(name) is not None
        ]
        if len(inputs) != 1:
            raise serializers.ValidationError(
                "Send exactly one of transcript, selected_option or cart_edit."
            )
        attrs["input_kind"] = inputs[0]
        return attrs
