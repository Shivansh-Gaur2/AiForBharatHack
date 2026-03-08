"""FastAPI routes for the AI Advisor service.

Endpoints handle conversation management, message processing,
quick analysis, and scenario analysis.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..domain.services import AIAdvisorService
from .schemas import (
    ConversationDetailResponse,
    ConversationListItem,
    ConversationResponse,
    MessageDTO,
    QuickAnalysisRequest,
    QuickAnalysisResponse,
    ScenarioAnalysisRequest,
    ScenarioAnalysisResponse,
    SendMessageRequest,
    StartConversationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-advisor", tags=["AI Advisor"])

# ---------------------------------------------------------------------------
# Dependency injection — set by main.py
# ---------------------------------------------------------------------------
_service: AIAdvisorService | None = None


def set_advisor_service(service: AIAdvisorService) -> None:
    global _service
    _service = service


def _get_service() -> AIAdvisorService:
    if _service is None:
        raise RuntimeError("AIAdvisorService not initialised")
    return _service


# ---------------------------------------------------------------------------
# Conversation Management
# ---------------------------------------------------------------------------

@router.post("/conversations", response_model=ConversationResponse)
async def start_conversation(req: StartConversationRequest):
    """Start a new AI advisor conversation.

    Optionally provide a profile ID to load borrower context,
    and/or an initial message to get an immediate AI response.
    """
    service = _get_service()
    result = await service.start_conversation(
        profile_id=req.profile_id,
        language=req.language,
        initial_message=req.message,
    )
    return ConversationResponse(**result)


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationResponse)
async def send_message(conversation_id: str, req: SendMessageRequest):
    """Send a message in an existing conversation and get an AI response."""
    service = _get_service()
    result = await service.send_message(
        conversation_id=conversation_id,
        user_message=req.message,
    )
    return ConversationResponse(**result)


@router.post("/conversations/{conversation_id}/messages/stream")
async def send_message_stream(conversation_id: str, req: SendMessageRequest):
    """Send a message and stream the AI response using Server-Sent Events.

    Returns a text/event-stream response where each event contains a
    token from the AI's response, enabling real-time display.
    """
    service = _get_service()

    async def event_generator():
        try:
            async for token in service.send_message_stream(
                conversation_id=conversation_id,
                user_message=req.message,
            ):
                # SSE format: data: <token>\n\n
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("Stream error: %s", exc)
            yield f"data: [ERROR] {str(exc)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str):
    """Retrieve a conversation with full message history."""
    service = _get_service()
    result = await service.get_conversation(conversation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailResponse(
        **{
            **result,
            "messages": [MessageDTO(**m) for m in result.get("messages", [])],
        }
    )


@router.get("/conversations/profile/{profile_id}")
async def get_profile_conversations(profile_id: str, limit: int = 10):
    """List conversations for a specific borrower profile."""
    service = _get_service()
    conversations = await service.get_conversations_for_profile(profile_id, limit)
    items = []
    for c in conversations:
        messages = c.get("messages", [])
        last_msg = messages[-1]["content"] if messages else None
        items.append(
            ConversationListItem(
                conversation_id=c["conversation_id"],
                profile_id=c.get("profile_id"),
                message_count=c.get("message_count", 0),
                language=c.get("language", "en"),
                created_at=c.get("created_at", 0),
                updated_at=c.get("updated_at", 0),
                last_message=last_msg[:100] if last_msg else None,
            )
        )
    return {"conversations": [item.model_dump() for item in items]}


# ---------------------------------------------------------------------------
# Quick Analysis (one-shot, no conversation)
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=QuickAnalysisResponse)
async def quick_analysis(req: QuickAnalysisRequest):
    """Generate a one-shot AI analysis for a borrower.

    Used by the dashboard to display an AI insight card.
    Does not create a conversation — it's a single prompt/response.
    """
    service = _get_service()
    result = await service.quick_analysis(profile_id=req.profile_id)
    return QuickAnalysisResponse(**result)


# ---------------------------------------------------------------------------
# Scenario Analysis
# ---------------------------------------------------------------------------

@router.post("/scenarios", response_model=ScenarioAnalysisResponse)
async def scenario_analysis(req: ScenarioAnalysisRequest):
    """Run an AI-powered what-if scenario analysis.

    Example scenarios:
    - "What if monsoon fails this year?"
    - "What if soybean prices drop by 30%?"
    - "What if I take a Rs 50,000 loan for tractor repair?"
    """
    service = _get_service()
    result = await service.analyze_scenario(
        profile_id=req.profile_id,
        scenario_description=req.scenario,
    )
    return ScenarioAnalysisResponse(**result)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-advisor"}
