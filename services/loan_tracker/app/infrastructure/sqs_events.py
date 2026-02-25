"""Factory for SNS-backed event publisher for the Loan Tracker service."""

from __future__ import annotations

from services.shared.events import AsyncEventPublisher, AsyncInMemoryEventPublisher


def create_loan_event_publisher(
    sns_topic_arn: str | None = None,
    region: str = "ap-south-1",
) -> AsyncEventPublisher:
    if not sns_topic_arn:
        return AsyncInMemoryEventPublisher()
    # TODO: Create an async SNS publisher for production
    return AsyncInMemoryEventPublisher()
