"""SQS/SNS event publishing adapter.

Implements the EventPublisher port using Amazon SNS for fan-out
to downstream service SQS queues.
"""

from __future__ import annotations

import logging
from typing import Any

from services.shared.events import SNSEventPublisher

logger = logging.getLogger(__name__)


def create_profile_event_publisher(
    sns_client: Any,
    topic_arn: str,
) -> SNSEventPublisher:
    """Factory to create the SNS publisher for profile events."""
    return SNSEventPublisher(sns_client=sns_client, topic_arn=topic_arn)
