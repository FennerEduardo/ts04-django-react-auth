"""Transactional outbox (Django ORM). Domain events are stored in the same transaction as state changes."""
import uuid

from django.db import models


class OutboxMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_id = models.CharField(max_length=128, db_index=True)
    event_type = models.CharField(max_length=128)
    version = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    occurred_on = models.DateTimeField()
    processed_on = models.DateTimeField(null=True, blank=True, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["occurred_on"]
        constraints = [models.UniqueConstraint(fields=["aggregate_id", "version"], name="outbox_unique_aggregate_version")]
