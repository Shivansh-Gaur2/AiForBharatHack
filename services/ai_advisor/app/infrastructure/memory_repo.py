"""In-memory conversation repository for local development.

Thread-safe via asyncio (single-threaded event loop).
"""

from __future__ import annotations

import logging

from services.shared.models import ProfileId

from ..domain.models import Conversation

logger = logging.getLogger(__name__)


class InMemoryConversationRepository:
    """Simple in-memory store for conversation history.

    Suitable for local development and testing.  In production, this
    would be replaced with a DynamoDB or Redis-backed implementation.
    """

    def __init__(self, max_conversations: int = 1000) -> None:
        self._store: dict[str, Conversation] = {}
        self._max = max_conversations

    async def save(self, conversation: Conversation) -> None:
        # Evict oldest if at capacity
        if len(self._store) >= self._max and conversation.conversation_id not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k].updated_at)
            del self._store[oldest_key]

        self._store[conversation.conversation_id] = conversation
        logger.debug(
            "Saved conversation %s (%d messages)",
            conversation.conversation_id,
            conversation.message_count,
        )

    async def find_by_id(self, conversation_id: str) -> Conversation | None:
        return self._store.get(conversation_id)

    async def find_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[Conversation]:
        matches = [
            c for c in self._store.values()
            if c.profile_id == profile_id
        ]
        matches.sort(key=lambda c: c.updated_at, reverse=True)
        return matches[:limit]

    async def delete(self, conversation_id: str) -> None:
        self._store.pop(conversation_id, None)
