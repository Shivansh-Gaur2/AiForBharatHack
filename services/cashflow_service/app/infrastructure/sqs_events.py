"""Factory for SNS-backed event publisher for the Cash Flow service."""

from __future__ import annotations

from services.shared.events import AsyncEventPublisher, AsyncInMemoryEventPublisher


def create_cashflow_event_publisher(
    sns_topic_arn: str | None = None,
    region: str = "ap-south-1",
) -> AsyncEventPublisher:
    """Create the event publisher for the Cash Flow service.

    Returns AsyncInMemoryEventPublisher for local dev (no SNS topic).
    In production, would use an async SNS adapter.
    """
    if not sns_topic_arn:
        return AsyncInMemoryEventPublisher()
    # Future: return AsyncSNSEventPublisher(...)
    return AsyncInMemoryEventPublisher()
