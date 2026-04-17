from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from apps.dispatch.services import trigger_dispatch_if_ready

from .models import Order
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    UpdateOrderStatusSerializer,
)


class OrderViewSet(ReadOnlyModelViewSet, GenericViewSet):
    queryset = Order.objects.select_related("vendor", "student").prefetch_related("items__menu_item").order_by("-created_at")
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create_order":
            return CreateOrderSerializer
        if self.action == "update_status":
            return UpdateOrderStatusSerializer
        return OrderSerializer

    @action(detail=False, methods=["post"], url_path="")
    def create_order(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        trigger_dispatch_if_ready(order)
        return Response(OrderSerializer(order).data)
