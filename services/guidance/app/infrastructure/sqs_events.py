"""Event publisher factory for the Guidance Service."""

from __future__ import annotations

import boto3

from services.shared.events import (
    AsyncEventPublisher,
    AsyncInMemoryEventPublisher,
    AsyncSNSEventPublisher,
)


def create_guidance_event_publisher(
    sns_topic_arn: str | None = None,
    aws_region: str = "ap-south-1",
) -> AsyncEventPublisher:
    """Return an async SNS publisher when a topic ARN is provided.

    Falls back to :class:`AsyncInMemoryEventPublisher` for local
    development where no SNS topic is configured.
    """
    if not sns_topic_arn:
        return AsyncInMemoryEventPublisher()
    sns_client = boto3.client("sns", region_name=aws_region)
    return AsyncSNSEventPublisher(sns_client=sns_client, topic_arn=sns_topic_arn)
