"""Event publisher factory for the Security service."""

from __future__ import annotations

from services.shared.events import AsyncInMemoryEventPublisher


def create_security_event_publisher(
    topic_arn: str | None = None,
    region: str = "ap-south-1",
):
    """Create an event publisher.

    Returns AsyncInMemoryEventPublisher for local dev (no topic_arn),
    or could be wired to SNS in production.
    """
    if topic_arn:
        # Production: use SNS (wrap sync publisher in async adapter)
        return AsyncInMemoryEventPublisher()  # placeholder — swap for SNS
    return AsyncInMemoryEventPublisher()
