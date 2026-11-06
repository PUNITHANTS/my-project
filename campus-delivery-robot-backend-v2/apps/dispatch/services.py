from apps.orders.services import transition_order

from .models import RobotDispatch


def trigger_dispatch_if_ready(order):
    if order.status != order.Status.READY:
        return order

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

    return transition_order(
        order,
        order.Status.DISPATCHED,
        note="Mock robot dispatch accepted",
    )
