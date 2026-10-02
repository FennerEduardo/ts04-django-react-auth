from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OutboxMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("aggregate_id", models.CharField(db_index=True, max_length=128)),
                ("event_type", models.CharField(max_length=128)),
                ("version", models.PositiveIntegerField()),
                ("payload", models.JSONField(default=dict)),
                ("occurred_on", models.DateTimeField()),
                ("processed_on", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["occurred_on"]},
        ),
        migrations.AddConstraint(
            model_name="outboxmessage",
            constraint=models.UniqueConstraint(fields=("aggregate_id", "version"), name="outbox_unique_aggregate_version"),
        ),
    ]
