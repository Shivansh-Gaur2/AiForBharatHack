"""Request/response schemas (Pydantic DTOs) for the AI Advisor API.

These live in the API layer — they serialize/deserialize HTTP payloads.
They are NOT domain entities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------

class StartConversationRequest(BaseModel):
    """Start a new AI advisor conversation."""
    profile_id: str | None = Field(
        default=None,
        description="Borrower profile ID to load context for personalised advice.",
    )
    language: str = Field(
        default="en",
        description="Language code: en, hi, ta, te, kn, mr, bn, gu, pa, or.",
    )
    message: str | None = Field(
        default=None,
        description="Optional first message. If omitted, a welcome message is generated.",
    )


class SendMessageRequest(BaseModel):
    """Send a message in an existing conversation."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message text.",
    )


class QuickAnalysisRequest(BaseModel):
    """Request a one-shot AI analysis for a borrower."""
    profile_id: str = Field(
        ...,
        description="Borrower profile ID to analyse.",
    )


class ScenarioAnalysisRequest(BaseModel):
    """Request an AI-powered scenario analysis."""
    profile_id: str = Field(
        ...,
        description="Borrower profile ID.",
    )
    scenario: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Natural-language description of the what-if scenario.",
    )


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    """Response after starting a conversation or sending a message."""
    conversation_id: str
    message: str
    intent: str | None = None
    profile_id: str | None = None
    has_context: bool = False


class MessageDTO(BaseModel):
    """A single message in conversation history."""
    role: str
    content: str
    timestamp: float
    metadata: dict | None = None


class ConversationDetailResponse(BaseModel):
    """Full conversation with message history."""
    conversation_id: str
    profile_id: str | None = None
    language: str = "en"
    message_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    messages: list[MessageDTO] = []


class QuickAnalysisResponse(BaseModel):
    """AI-generated borrower analysis."""
    profile_id: str
    analysis: str
    has_context: bool = False
    success: bool = True


class ScenarioAnalysisResponse(BaseModel):
    """AI-generated scenario analysis."""
    profile_id: str
    scenario: str
    analysis: str
    has_context: bool = False


class ConversationListItem(BaseModel):
    """Summary of a conversation for list views."""
    conversation_id: str
    profile_id: str | None = None
    message_count: int = 0
    language: str = "en"
    created_at: float = 0.0
    updated_at: float = 0.0
    last_message: str | None = None
