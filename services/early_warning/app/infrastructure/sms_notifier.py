"""SMS Notification adapters for the Early Warning service.

Provides two implementations of the SmsNotifier port:
- SnsSmsNotifier  — production: dispatches via AWS SNS (direct SMS)
- StubSmsNotifier — local dev: logs messages without sending

Both are fire-and-forget; failures are logged and silently swallowed
so that the alert pipeline is never blocked by a notification error.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StubSmsNotifier:
    """Local development stub — logs SMS messages without sending."""

    async def send_alert_sms(self, phone_number: str, message: str) -> bool:
        logger.info(
            "[StubSMS] To=%s Message=%s",
            phone_number,
            message[:120],
        )
        return True


class SnsSmsNotifier:
    """Production adapter — sends SMS via AWS SNS ``publish`` API.

    Uses SNS direct SMS publishing (``PhoneNumber`` parameter),
    not topic-based delivery.

    Attributes:
        sender_id: Alphanumeric sender ID (max 11 chars, e.g. 'RURALADV').
        sms_type: 'Transactional' (guaranteed delivery) or 'Promotional'.
    """

    def __init__(
        self,
        region_name: str = "ap-south-1",
        sender_id: str = "RURALADV",
        sms_type: str = "Transactional",
    ) -> None:
        import boto3

        self._client: Any = boto3.client("sns", region_name=region_name)
        self._sender_id = sender_id
        self._sms_type = sms_type

    async def send_alert_sms(self, phone_number: str, message: str) -> bool:
        """Publish SMS via SNS. Returns True on success, False on failure."""
        try:
            self._client.publish(
                PhoneNumber=phone_number,
                Message=message[:160],  # SMS length limit
                MessageAttributes={
                    "AWS.SNS.SMS.SenderID": {
                        "DataType": "String",
                        "StringValue": self._sender_id,
                    },
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": self._sms_type,
                    },
                },
            )
            logger.info("SMS sent to %s", phone_number)
            return True
        except Exception:
            logger.warning("Failed to send SMS to %s", phone_number, exc_info=True)
            return False


def create_sms_notifier(
    enabled: bool = False,
    region_name: str = "ap-south-1",
    sender_id: str = "RURALADV",
) -> StubSmsNotifier | SnsSmsNotifier:
    """Factory — returns stub for local dev, SNS adapter for production."""
    if enabled:
        return SnsSmsNotifier(region_name=region_name, sender_id=sender_id)
    return StubSmsNotifier()
