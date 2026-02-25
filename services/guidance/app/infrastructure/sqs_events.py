"""Event publisher factory for the Guidance Service."""

from __future__ import annotations

from services.shared.events import AsyncInMemoryEventPublisher


def create_guidance_event_publisher(
    sns_topic_arn: str | None = None,
    aws_region: str = "ap-south-1",
) -> AsyncInMemoryEventPublisher:
    """Create the event publisher.

    Currently returns in-memory publisher; will be replaced with
    SNS publisher when infrastructure is ready.
    """
    return AsyncInMemoryEventPublisher()
