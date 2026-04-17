from apps.notifications.services import broadcast_order_update

from .models import RobotDispatch


def trigger_dispatch_if_ready(order) -> None:
    if order.status != order.Status.READY:
        return

    dispatch, _ = RobotDispatch.objects.get_or_create(
        order=order,
        defaults={
            "provider": RobotDispatch.Provider.ROBOT,
            "status": RobotDispatch.Status.SENT,
            "request_payload": {
                "order_id": order.id,
                "pickup_location": order.vendor.location_label,
                "dropoff_location": order.delivery_location,
            },
            "response_payload": {"message": "Mock dispatch accepted"},
        },
    )

    if dispatch.status != RobotDispatch.Status.SENT:
        dispatch.status = RobotDispatch.Status.SENT
        dispatch.response_payload = {"message": "Mock dispatch accepted"}
        dispatch.save(update_fields=["status", "response_payload", "updated_at"])

    order.status = order.Status.DISPATCHED
    order.save(update_fields=["status", "updated_at"])
    broadcast_order_update(order)
