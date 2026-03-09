"""SQS/SNS event bus abstraction.

Provides a clean interface for publishing domain events.
Infrastructure details (boto3, SQS URLs) are encapsulated here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Event
# ---------------------------------------------------------------------------
@dataclass
class DomainEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    timestamp: str = ""
    event_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()
        if not self.event_id:
            import uuid
            self.event_id = str(uuid.uuid4())

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


# ---------------------------------------------------------------------------
# Publisher Port (domain-facing interface)
# ---------------------------------------------------------------------------
class EventPublisher(Protocol):
    """Abstract port — domain services depend on this, not on SQS/SNS."""

    def publish(self, event: DomainEvent) -> None: ...


# ---------------------------------------------------------------------------
# In-Memory Publisher (for testing)
# ---------------------------------------------------------------------------
class InMemoryEventPublisher:
    """Collects events in memory — perfect for unit tests."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
        logger.debug("InMemory event published: %s", event.event_type)


# ---------------------------------------------------------------------------
# Async Publisher Port (for async services like Loan Tracker, Risk)
# ---------------------------------------------------------------------------
class AsyncEventPublisher(Protocol):
    """Async variant of the event publisher port."""

    async def publish(self, event: DomainEvent) -> None: ...


class AsyncInMemoryEventPublisher:
    """Async in-memory event publisher for unit tests of async services."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
        logger.debug("AsyncInMemory event published: %s", event.event_type)


# ---------------------------------------------------------------------------
# SNS Publishers (production adapters)
# ---------------------------------------------------------------------------
class SNSEventPublisher:
    """Publishes domain events to an SNS topic."""

    def __init__(self, sns_client: Any, topic_arn: str) -> None:
        self._sns = sns_client
        self._topic_arn = topic_arn

    def publish(self, event: DomainEvent) -> None:
        try:
            self._sns.publish(
                TopicArn=self._topic_arn,
                Message=event.to_json(),
                MessageAttributes={
                    "event_type": {
                        "DataType": "String",
                        "StringValue": event.event_type,
                    }
                },
            )
            logger.info(
                "Published event %s to %s", event.event_type, self._topic_arn
            )
        except Exception:
            # Log-and-swallow — domain work already succeeded;
            # downstream consumers will eventually catch up via a
            # DLQ replay or polling reconciliation.
            logger.exception(
                "Failed to publish event %s (aggregate=%s) to %s — "
                "message will be retried via DLQ reconciliation",
                event.event_type,
                event.aggregate_id,
                self._topic_arn,
            )


class AsyncSNSEventPublisher:
    """Async adapter for publishing domain events to SNS.

    Wraps the synchronous boto3 SNS ``publish`` call in
    ``asyncio.to_thread`` so FastAPI route handlers (which are async)
    do not block the event loop.

    Fire-and-forget semantics: a publish failure is logged but does
    **not** propagate to the caller, keeping domain operations
    resilient to messaging outages.
    """

    def __init__(self, sns_client: Any, topic_arn: str) -> None:
        self._sns = sns_client
        self._topic_arn = topic_arn

    async def publish(self, event: DomainEvent) -> None:  # noqa: D401
        import asyncio

        try:
            await asyncio.to_thread(self._sync_publish, event)
        except Exception:
            # Log-and-swallow — domain work already succeeded;
            # downstream consumers will eventually catch up via a
            # DLQ replay or polling reconciliation.
            logger.exception(
                "Failed to publish event %s (aggregate=%s) to %s — "
                "message will be retried via DLQ reconciliation",
                event.event_type,
                event.aggregate_id,
                self._topic_arn,
            )

    # -- private helpers ----------------------------------------------------

    def _sync_publish(self, event: DomainEvent) -> None:
        self._sns.publish(
            TopicArn=self._topic_arn,
            Message=event.to_json(),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": event.event_type,
                },
                "aggregate_id": {
                    "DataType": "String",
                    "StringValue": event.aggregate_id,
                },
            },
        )
        logger.info(
            "Published event %s (aggregate=%s) to %s",
            event.event_type,
            event.aggregate_id,
            self._topic_arn,
        )
