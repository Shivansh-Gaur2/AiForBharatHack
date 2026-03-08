"""Port interfaces for the AI Advisor service.

All ports are Protocol classes — infrastructure adapters implement them.
Domain code depends only on these abstractions.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from services.shared.models import ProfileId

from .models import BorrowerContext, Conversation


# ---------------------------------------------------------------------------
# LLM Provider Port
# ---------------------------------------------------------------------------

class LLMProvider(Protocol):
    """Abstraction over any LLM backend (Bedrock, OpenAI, local, etc.)."""

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> str:
        """Generate a completion given system prompt and message history."""
        ...

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        """Stream a completion token-by-token."""
        ...


# ---------------------------------------------------------------------------
# Data Aggregator Port
# ---------------------------------------------------------------------------

class DataAggregator(Protocol):
    """Fetches and aggregates borrower data from all micro-services."""

    async def fetch_profile(self, profile_id: ProfileId) -> dict[str, Any]:
        """Fetch profile summary from Profile Service."""
        ...

    async def fetch_risk(self, profile_id: ProfileId) -> dict[str, Any]:
        """Fetch risk assessment from Risk Assessment Service."""
        ...

    async def fetch_cashflow(self, profile_id: ProfileId) -> dict[str, Any]:
        """Fetch cash-flow forecast and repayment capacity."""
        ...

    async def fetch_loans(self, profile_id: ProfileId) -> dict[str, Any]:
        """Fetch loan exposure from Loan Tracker Service."""
        ...

    async def fetch_alerts(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        """Fetch active alerts from Early Warning Service."""
        ...

    async def fetch_guidance(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        """Fetch active guidance from Guidance Service."""
        ...

    async def build_full_context(self, profile_id: ProfileId) -> BorrowerContext:
        """Aggregate all services into a single BorrowerContext."""
        ...


# ---------------------------------------------------------------------------
# Conversation Repository Port
# ---------------------------------------------------------------------------

class ConversationRepository(Protocol):
    """Persistence port for conversation history."""

    async def save(self, conversation: Conversation) -> None: ...

    async def find_by_id(self, conversation_id: str) -> Conversation | None: ...

    async def find_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[Conversation]: ...

    async def delete(self, conversation_id: str) -> None: ...
