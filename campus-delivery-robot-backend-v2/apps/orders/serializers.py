from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import signing
from django.core.cache import cache
from django.db import transaction

from apps.conversational_ordering.menu_validation import validate_order_submission
from apps.conversational_ordering.schemas import ParsedOrder
from apps.conversational_ordering.services import (
    CONFIRMATION_SALT,
    confirmed_cart_signature,
    submission_cart_signature,
)
from apps.conversational_ordering.sessions import cache_key
from apps.menu.models import MenuItem
from apps.notifications.services import broadcast_order_update
from apps.vendors.models import Vendor

from .models import Order, OrderItem, OrderStatusHistory


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
    status_history = serializers.SerializerMethodField()

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
            "status_history",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "created_at", "updated_at")

    def get_status_history(self, order):
        return [
            {
                "previous_status": row.previous_status,
                "status": row.status,
                "actor_id": row.actor_id,
                "note": row.note,
                "created_at": row.created_at,
            }
            for row in order.status_history.all()
        ]


class CreateOrderSerializer(serializers.Serializer):
    student_name = serializers.CharField()
    phone = serializers.CharField()
    vendor_id = serializers.IntegerField()
    delivery_location = serializers.CharField()
    items = OrderItemWriteSerializer(many=True)
    ai_session_id = serializers.UUIDField(required=False)
    confirmation_token = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        has_session = "ai_session_id" in attrs
        has_token = "confirmation_token" in attrs
        if has_session != has_token:
            raise serializers.ValidationError(
                "AI orders require both ai_session_id and confirmation_token."
            )

        errors = validate_order_submission(
            attrs["vendor_id"], attrs["delivery_location"], attrs["items"]
        )
        if errors:
            raise serializers.ValidationError({"items": errors})

        if has_session:
            self._validate_ai_confirmation(attrs)
        return attrs

    def _validate_ai_confirmation(self, attrs):
        request = self.context["request"]
        session_id = str(attrs["ai_session_id"])
        try:
            claims = signing.loads(
                attrs["confirmation_token"],
                salt=CONFIRMATION_SALT,
                max_age=300,
            )
        except signing.BadSignature as exc:
            raise serializers.ValidationError(
                {"confirmation_token": "The confirmation expired or is invalid. Review the cart again."}
            ) from exc

        submitted_signature = submission_cart_signature(
            attrs["vendor_id"], attrs["delivery_location"], attrs["items"]
        )
        if (
            claims.get("session_id") != session_id
            or claims.get("user_id") != request.user.pk
            or claims.get("cart") != submitted_signature
        ):
            raise serializers.ValidationError(
                {"confirmation_token": "The submitted cart differs from the confirmed cart."}
            )

        state = cache.get(cache_key(session_id))
        if (
            not state
            or state.get("user_id") != request.user.pk
            or state.get("submitted_order_id")
        ):
            raise serializers.ValidationError(
                {"ai_session_id": "This conversation is expired or has already been submitted."}
            )
        parsed = ParsedOrder.model_validate(state["draft_order"])
        current_signature = confirmed_cart_signature(parsed, attrs["vendor_id"])
        if current_signature != submitted_signature:
            raise serializers.ValidationError(
                {"confirmation_token": "The conversation draft changed. Review and confirm it again."}
            )

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        vendor_id = validated_data.pop("vendor_id")
        ai_session_id = validated_data.pop("ai_session_id", None)
        validated_data.pop("confirmation_token", None)
        student = self.context["request"].user

        if ai_session_id and not cache.add(
            f"order-submit-lock:{ai_session_id}", True, timeout=300
        ):
            raise serializers.ValidationError("This AI order is already being submitted.")

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    vendor_id=vendor_id, student=student, **validated_data
                )
                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status="",
                    status=Order.Status.PLACED,
                    actor=student,
                    note="Order placed",
                )
                for item_data in items_data:
                    menu_item = MenuItem.objects.get(pk=item_data["menu_item_id"])
                    OrderItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=item_data["quantity"],
                        customization=item_data.get("customization", ""),
                        price_at_order=menu_item.price,
                    )
                if ai_session_id:
                    key = cache_key(ai_session_id)
                    def mark_session_submitted():
                        state = cache.get(key)
                        if state:
                            state["submitted_order_id"] = order.pk
                            cache.set(key, state, timeout=900)
                        cache.delete(f"order-submit-lock:{ai_session_id}")

                    transaction.on_commit(mark_session_submitted)
                transaction.on_commit(lambda: broadcast_order_update(order))
        except Exception:
            if ai_session_id:
                cache.delete(f"order-submit-lock:{ai_session_id}")
            raise
        return order


class UpdateOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY, Order.Status.REJECTED]
    )
    vendor_note = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        from .services import transition_order

        try:
            return transition_order(
                instance,
                validated_data["status"],
                actor=self.context["request"].user,
                note=validated_data.get("vendor_note", ""),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"status": exc.messages}) from exc
