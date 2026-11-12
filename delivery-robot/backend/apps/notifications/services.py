from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_order_update(order) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        "orders",
        {
            "type": "order_update",
            "payload": {
                "id": order.id,
                "status": order.status,
                "vendor_id": order.vendor_id,
                "delivery_location": order.delivery_location,
                "updated_at": order.updated_at.isoformat(),
            },
        },
    )
