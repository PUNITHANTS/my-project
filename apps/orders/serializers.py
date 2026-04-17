from rest_framework import serializers

from apps.menu.models import MenuItem
from apps.notifications.services import broadcast_order_update

from .models import Order, OrderItem


class OrderItemWriteSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    customization = serializers.CharField(required=False, allow_blank=True)


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "menu_item", "menu_item_name", "quantity", "customization", "price_at_order")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "student",
            "student_name",
            "phone",
            "vendor",
            "delivery_location",
            "status",
            "vendor_note",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "created_at", "updated_at")


class CreateOrderSerializer(serializers.Serializer):
    student_name = serializers.CharField()
    phone = serializers.CharField()
    vendor_id = serializers.IntegerField()
    delivery_location = serializers.CharField()
    items = OrderItemWriteSerializer(many=True)

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        vendor_id = validated_data.pop("vendor_id")
        order = Order.objects.create(vendor_id=vendor_id, **validated_data)

        for item_data in items_data:
            menu_item = MenuItem.objects.get(pk=item_data["menu_item_id"])
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item_data["quantity"],
                customization=item_data.get("customization", ""),
                price_at_order=menu_item.price,
            )

        broadcast_order_update(order)
        return order


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY, Order.Status.REJECTED]
    )
    vendor_note = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        instance.status = validated_data["status"]
        instance.vendor_note = validated_data.get("vendor_note", "")
        instance.save(update_fields=["status", "vendor_note", "updated_at"])
        broadcast_order_update(instance)
        return instance
