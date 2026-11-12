from django.core.exceptions import ValidationError
from django.db import transaction

from apps.notifications.services import broadcast_order_update

from .models import Order, OrderStatusHistory


ALLOWED_TRANSITIONS = {
    Order.Status.PLACED: {Order.Status.ACCEPTED, Order.Status.REJECTED, Order.Status.CANCELLED},
    Order.Status.ACCEPTED: {Order.Status.PREPARING},
    Order.Status.PREPARING: {Order.Status.READY},
    Order.Status.READY: {Order.Status.DISPATCHED, Order.Status.FALLBACK},
    Order.Status.DISPATCHED: {Order.Status.DELIVERED, Order.Status.FALLBACK},
    Order.Status.FALLBACK: {Order.Status.DELIVERED, Order.Status.CANCELLED},
}


@transaction.atomic
def transition_order(order, new_status, actor=None, note=""):
    locked = Order.objects.select_for_update().get(pk=order.pk)
    if new_status not in ALLOWED_TRANSITIONS.get(locked.status, set()):
        raise ValidationError(
            f"Order cannot transition from {locked.status} to {new_status}."
        )
    previous_status = locked.status
    locked.status = new_status
    if note:
        locked.vendor_note = note
    locked.save(update_fields=["status", "vendor_note", "updated_at"])
    OrderStatusHistory.objects.create(
        order=locked,
        previous_status=previous_status,
        status=new_status,
        actor=actor,
        note=note,
    )
    transaction.on_commit(lambda: broadcast_order_update(locked))
    return locked
