"""Factory for SNS-backed event publisher for the Loan Tracker service."""

from __future__ import annotations

import boto3

from services.shared.events import (
    AsyncEventPublisher,
    AsyncInMemoryEventPublisher,
    AsyncSNSEventPublisher,
)


def create_loan_event_publisher(
    sns_topic_arn: str | None = None,
    region: str = "ap-south-1",
    endpoint_url: str | None = None,
) -> AsyncEventPublisher:
    """Return an async SNS publisher when a topic ARN is provided.

    Falls back to :class:`AsyncInMemoryEventPublisher` for local
    development where no SNS topic is configured.
    """
    if not sns_topic_arn:
        return AsyncInMemoryEventPublisher()
    kwargs: dict = {"region_name": region}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    sns_client = boto3.client("sns", **kwargs)
    return AsyncSNSEventPublisher(sns_client=sns_client, topic_arn=sns_topic_arn)
