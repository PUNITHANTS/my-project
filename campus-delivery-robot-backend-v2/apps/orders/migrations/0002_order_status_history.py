import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def initialize_existing_order_history(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderStatusHistory = apps.get_model("orders", "OrderStatusHistory")
    database = schema_editor.connection.alias
    batch = []
    for order in Order.objects.using(database).only("pk", "status").iterator(chunk_size=500):
        batch.append(
            OrderStatusHistory(
                order_id=order.pk,
                previous_status="",
                status=order.status,
                actor_id=None,
                note="Status history initialized during migration",
            )
        )
        if len(batch) == 500:
            OrderStatusHistory.objects.using(database).bulk_create(batch, batch_size=500)
            batch.clear()
    if batch:
        OrderStatusHistory.objects.using(database).bulk_create(batch, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(blank=True, max_length=20)),
                ("status", models.CharField(choices=[("PLACED", "Placed"), ("ACCEPTED", "Accepted"), ("PREPARING", "Preparing"), ("READY", "Ready"), ("DISPATCHED", "Dispatched"), ("DELIVERED", "Delivered"), ("REJECTED", "Rejected"), ("FALLBACK", "Fallback"), ("CANCELLED", "Cancelled")], max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_status_changes", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="orders.order")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.RunPython(
            initialize_existing_order_history,
            migrations.RunPython.noop,
        ),
    ]
