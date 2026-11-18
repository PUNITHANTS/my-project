import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("conversational_ordering", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="aiconversationturn",
            name="turn_id",
            field=models.UUIDField(db_index=True, default=uuid.uuid4),
        ),
        migrations.AddField(
            model_name="aiconversationturn",
            name="input_kind",
            field=models.CharField(
                choices=[
                    ("transcript", "Typed or spoken text"),
                    ("selected_option", "Tapped option"),
                    ("cart_edit", "Cart edit"),
                ],
                default="transcript",
                max_length=20,
            ),
        ),
    ]
