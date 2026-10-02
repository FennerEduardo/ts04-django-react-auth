"""Persists an aggregate's pending events into the outbox atomically."""
from django.db import transaction

from app.models import OutboxMessage


def save_pending_events(aggregate) -> int:
    with transaction.atomic():
        for event in aggregate.pending_events:
            OutboxMessage.objects.create(
                aggregate_id=event.aggregate_id,
                event_type=event.type.value,
                version=event.version,
                payload=event.payload,
                occurred_on=event.occurred_on,
            )
    return len(aggregate.pending_events)
