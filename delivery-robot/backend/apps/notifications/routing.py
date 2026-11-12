from django.urls import path

from .consumers import OrderUpdatesConsumer


websocket_urlpatterns = [
    path("ws/orders/", OrderUpdatesConsumer.as_asgi()),
]
