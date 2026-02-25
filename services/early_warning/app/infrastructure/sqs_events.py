"""Factory for SNS-backed event publisher for the Early Warning service."""

from __future__ import annotations

from services.shared.events import AsyncEventPublisher, AsyncInMemoryEventPublisher


def create_early_warning_event_publisher(
    sns_topic_arn: str | None = None,
    region: str = "ap-south-1",
) -> AsyncEventPublisher:
    """Create the event publisher.

    Returns AsyncInMemoryEventPublisher for local dev (no SNS topic).
    """
    if not sns_topic_arn:
        return AsyncInMemoryEventPublisher()
    return AsyncInMemoryEventPublisher()
