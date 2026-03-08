"""DynamoDB conversation repository for the AI Advisor service.

Single-table design with access patterns:
  PK=CONVERSATION#{conversation_id}      SK=METADATA         → conversation record
  PK=PROFILE_CONVERSATIONS#{profile_id}  SK=TS#{iso}#{id}    → profile index
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from services.shared.models import ProfileId

from ..domain.models import (
    BorrowerContext,
    Conversation,
    Message,
    MessageRole,
)

logger = logging.getLogger(__name__)


class DynamoDBConversationRepository:
    """DynamoDB-backed conversation store.

    Mirrors the InMemoryConversationRepository interface but persists
    data to DynamoDB Local (dev) or real DynamoDB (prod).
    """

    def __init__(self, dynamodb_resource: Any, table_name: str) -> None:
        self._table = dynamodb_resource.Table(table_name)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    async def save(self, conversation: Conversation) -> None:
        item = self._to_item(conversation)
        self._table.put_item(Item=item)

        # Profile index — allows listing recent conversations per borrower
        if conversation.profile_id:
            ts = datetime.fromtimestamp(conversation.created_at, tz=UTC).isoformat()
            self._table.put_item(Item={
                "PK": f"PROFILE_CONVERSATIONS#{conversation.profile_id}",
                "SK": f"TS#{ts}#{conversation.conversation_id}",
                "conversation_id": conversation.conversation_id,
                "profile_id": conversation.profile_id,
                "message_count": conversation.message_count,
                "language": conversation.language,
                "created_at": Decimal(str(conversation.created_at)),
                "updated_at": Decimal(str(conversation.updated_at)),
            })

        logger.debug(
            "Saved conversation %s (%d messages) to DynamoDB",
            conversation.conversation_id,
            conversation.message_count,
        )

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------

    async def find_by_id(self, conversation_id: str) -> Conversation | None:
        resp = self._table.get_item(Key={
            "PK": f"CONVERSATION#{conversation_id}",
            "SK": "METADATA",
        })
        item = resp.get("Item")
        if not item:
            return None
        return self._from_item(item)

    async def find_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[Conversation]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={
                ":pk": f"PROFILE_CONVERSATIONS#{profile_id}",
            },
            ScanIndexForward=False,  # newest first
            Limit=limit,
        )
        result: list[Conversation] = []
        for index_item in resp.get("Items", []):
            cid = index_item["conversation_id"]
            conv = await self.find_by_id(cid)
            if conv:
                result.append(conv)
        return result

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, conversation_id: str) -> None:
        # Look up conversation first to clean up profile index
        conv = await self.find_by_id(conversation_id)
        if not conv:
            return

        # Delete main record
        self._table.delete_item(Key={
            "PK": f"CONVERSATION#{conversation_id}",
            "SK": "METADATA",
        })

        # Delete from profile index
        if conv.profile_id:
            ts = datetime.fromtimestamp(conv.created_at, tz=UTC).isoformat()
            self._table.delete_item(Key={
                "PK": f"PROFILE_CONVERSATIONS#{conv.profile_id}",
                "SK": f"TS#{ts}#{conversation_id}",
            })

    # ------------------------------------------------------------------
    # Serialization: Domain → DynamoDB
    # ------------------------------------------------------------------

    def _to_item(self, conv: Conversation) -> dict[str, Any]:
        messages = [
            {
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp,
                "metadata": json.dumps(m.metadata) if m.metadata else "{}",
            }
            for m in conv.messages
        ]

        # Serialize context as a JSON string to avoid DynamoDB nested-map limits
        context_data = {}
        if conv.context:
            context_data = {
                "profile_id": conv.context.profile_id,
                "profile_summary": conv.context.profile_summary,
                "risk_assessment": conv.context.risk_assessment,
                "cashflow_forecast": conv.context.cashflow_forecast,
                "repayment_capacity": conv.context.repayment_capacity,
                "loan_exposure": conv.context.loan_exposure,
                "active_loans": conv.context.active_loans,
                "active_alerts": conv.context.active_alerts,
                "active_guidance": conv.context.active_guidance,
            }

        return {
            "PK": f"CONVERSATION#{conv.conversation_id}",
            "SK": "METADATA",
            "conversation_id": conv.conversation_id,
            "profile_id": conv.profile_id or "",
            "messages": json.dumps(messages),
            "context": json.dumps(context_data),
            "language": conv.language,
            "created_at": Decimal(str(conv.created_at)),
            "updated_at": Decimal(str(conv.updated_at)),
        }

    # ------------------------------------------------------------------
    # Deserialization: DynamoDB → Domain
    # ------------------------------------------------------------------

    def _from_item(self, item: dict[str, Any]) -> Conversation:
        # Deserialize messages
        messages_raw = json.loads(item.get("messages", "[]"))
        messages = [
            Message(
                role=MessageRole(m["role"]),
                content=m["content"],
                timestamp=float(m.get("timestamp", 0)),
                metadata=json.loads(m.get("metadata", "{}")) if isinstance(m.get("metadata"), str) else m.get("metadata", {}),
            )
            for m in messages_raw
        ]

        # Deserialize context
        context_raw = json.loads(item.get("context", "{}"))
        context = BorrowerContext(
            profile_id=context_raw.get("profile_id"),
            profile_summary=context_raw.get("profile_summary"),
            risk_assessment=context_raw.get("risk_assessment"),
            cashflow_forecast=context_raw.get("cashflow_forecast"),
            repayment_capacity=context_raw.get("repayment_capacity"),
            loan_exposure=context_raw.get("loan_exposure"),
            active_loans=context_raw.get("active_loans", []),
            active_alerts=context_raw.get("active_alerts", []),
            active_guidance=context_raw.get("active_guidance", []),
        )

        profile_id = item.get("profile_id", "") or None

        return Conversation(
            conversation_id=item["conversation_id"],
            profile_id=profile_id,
            messages=messages,
            context=context,
            language=item.get("language", "en"),
            created_at=float(item.get("created_at", 0)),
            updated_at=float(item.get("updated_at", 0)),
        )
