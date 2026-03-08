"""Application service for the AI Advisor.

Orchestrates conversation flow: intent classification, context assembly,
prompt construction, LLM invocation, and response handling.

This is the central brain of the AI layer — it ties together all the
micro-services into a coherent conversational experience.
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator

from services.shared.models import ProfileId

from .interfaces import ConversationRepository, DataAggregator, LLMProvider
from .models import (
    BorrowerContext,
    Conversation,
    ConversationIntent,
    INTENT_SERVICES,
    Message,
)
from .prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    SYSTEM_PROMPT,
    build_contextual_prompt,
    build_quick_analysis_prompt,
    build_scenario_prompt,
)

logger = logging.getLogger(__name__)

# Context TTL: only re-fetch from services if data is older than this
_CONTEXT_TTL_SECONDS = 60.0


class AIAdvisorService:
    """Application service — orchestrates AI advisor conversation workflows.

    Responsibilities:
    1. Manage conversation lifecycle (create, continue, retrieve)
    2. Classify user intent to determine what data to fetch
    3. Aggregate borrower data from micro-services
    4. Construct context-rich prompts
    5. Invoke LLM and return responses
    """

    def __init__(
        self,
        llm: LLMProvider,
        aggregator: DataAggregator,
        repo: ConversationRepository,
    ) -> None:
        self._llm = llm
        self._aggregator = aggregator
        self._repo = repo

    # ------------------------------------------------------------------
    # Command: Start a new conversation
    # ------------------------------------------------------------------

    async def start_conversation(
        self,
        profile_id: ProfileId | None = None,
        language: str = "en",
        initial_message: str | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation, optionally pre-loading borrower context."""
        conversation = Conversation(
            profile_id=profile_id,
            language=language,
        )

        # Pre-load context if a profile is provided
        if profile_id:
            try:
                conversation.context = await self._aggregator.build_full_context(profile_id)
                logger.info("Pre-loaded context for profile %s", profile_id)
            except Exception as exc:
                logger.warning("Failed to pre-load context for %s: %s", profile_id, exc)

        # Generate welcome message
        if initial_message:
            return await self._process_message(conversation, initial_message)

        welcome = self._build_welcome(conversation)
        conversation.add_assistant_message(welcome)
        await self._repo.save(conversation)

        return {
            "conversation_id": conversation.conversation_id,
            "message": welcome,
            "profile_id": profile_id,
            "has_context": conversation.context.has_data(),
        }

    # ------------------------------------------------------------------
    # Command: Send a message in an existing conversation
    # ------------------------------------------------------------------

    async def send_message(
        self,
        conversation_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        """Process a user message and generate an AI response."""
        conversation = await self._repo.find_by_id(conversation_id)
        if not conversation:
            # Auto-create if not found (stateless fallback)
            conversation = Conversation(conversation_id=conversation_id)

        return await self._process_message(conversation, user_message)

    # ------------------------------------------------------------------
    # Command: Send a message (streaming)
    # ------------------------------------------------------------------

    async def send_message_stream(
        self,
        conversation_id: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        """Process a user message and stream the AI response token-by-token."""
        conversation = await self._repo.find_by_id(conversation_id)
        if not conversation:
            conversation = Conversation(conversation_id=conversation_id)

        conversation.add_user_message(user_message)

        # Classify intent and refresh context if needed
        intent = await self._classify_intent(user_message)
        if conversation.profile_id and not conversation.context.has_data():
            try:
                conversation.context = await self._aggregator.build_partial_context(
                    conversation.profile_id,
                    self._services_for_intent(intent),
                )
            except Exception as exc:
                logger.warning("Context fetch failed: %s", exc)

        # Build the prompt
        contextual_prompt = build_contextual_prompt(
            user_message=user_message,
            context=conversation.context,
            intent=intent,
            language=conversation.language,
        )

        messages = conversation.get_message_history()
        # Replace last user message with the enriched version
        if messages and messages[-1]["role"] == "user":
            messages[-1] = {"role": "user", "content": contextual_prompt}
        else:
            messages.append({"role": "user", "content": contextual_prompt})

        # Stream from LLM
        full_response = []
        async for token in self._llm.generate_stream(
            system_prompt=SYSTEM_PROMPT,
            messages=messages,
            max_tokens=600,
            temperature=0.4,
        ):
            full_response.append(token)
            yield token

        # Save the complete response
        response_text = "".join(full_response)
        conversation.add_assistant_message(
            response_text,
            metadata={"intent": intent.value},
        )
        await self._repo.save(conversation)

    # ------------------------------------------------------------------
    # Query: Get conversation history
    # ------------------------------------------------------------------

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Retrieve a conversation by ID."""
        conv = await self._repo.find_by_id(conversation_id)
        if not conv:
            return None
        return self._serialize_conversation(conv)

    async def get_conversations_for_profile(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve conversations for a profile."""
        conversations = await self._repo.find_by_profile(profile_id, limit)
        return [self._serialize_conversation(c) for c in conversations]

    # ------------------------------------------------------------------
    # Query: Quick AI analysis (no conversation, one-shot)
    # ------------------------------------------------------------------

    async def quick_analysis(self, profile_id: ProfileId) -> dict[str, Any]:
        """Generate a one-shot AI analysis for a borrower's dashboard.

        This doesn't create a conversation — it's a single prompt/response
        for displaying an insight card on the dashboard.
        """
        try:
            context = await self._aggregator.build_full_context(profile_id)
        except Exception as exc:
            logger.warning("Failed to fetch context for quick analysis: %s", exc)
            return {
                "profile_id": profile_id,
                "analysis": "Unable to generate analysis — some services may be unavailable.",
                "success": False,
            }

        prompt = build_quick_analysis_prompt(context)
        try:
            response = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
        except Exception as exc:
            logger.warning("LLM call failed for quick analysis: %s", exc)
            response = self._fallback_analysis(context)

        return {
            "profile_id": profile_id,
            "analysis": response,
            "has_context": context.has_data(),
            "success": True,
        }

    # ------------------------------------------------------------------
    # Query: AI scenario analysis
    # ------------------------------------------------------------------

    async def analyze_scenario(
        self,
        profile_id: ProfileId,
        scenario_description: str,
    ) -> dict[str, Any]:
        """Run an AI-powered what-if scenario analysis."""
        try:
            context = await self._aggregator.build_full_context(profile_id)
        except Exception as exc:
            logger.warning("Context fetch failed for scenario: %s", exc)
            context = BorrowerContext(profile_id=profile_id)

        prompt = build_scenario_prompt(context, scenario_description)
        try:
            response = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("LLM call failed for scenario: %s", exc)
            response = (
                "I'm unable to analyze this scenario right now. "
                "Please try again or consult with your bank officer."
            )

        return {
            "profile_id": profile_id,
            "scenario": scenario_description,
            "analysis": response,
            "has_context": context.has_data(),
        }

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    async def _process_message(
        self,
        conversation: Conversation,
        user_message: str,
    ) -> dict[str, Any]:
        """Core message processing pipeline."""
        conversation.add_user_message(user_message)

        # Step 1: Classify intent
        intent = await self._classify_intent(user_message)
        logger.info("Classified intent: %s", intent.value)

        # Step 2: Fetch/refresh context if profile is linked
        if conversation.profile_id and self._should_refresh_context(intent, conversation):
            try:
                conversation.context = await self._aggregator.build_partial_context(
                    conversation.profile_id,
                    self._services_for_intent(intent),
                )
            except Exception as exc:
                logger.warning("Context refresh failed: %s", exc)

        # Step 3: Build contextual prompt
        contextual_prompt = build_contextual_prompt(
            user_message=user_message,
            context=conversation.context,
            intent=intent,
            language=conversation.language,
        )

        # Step 4: Build message history for LLM
        messages = conversation.get_message_history()
        # Replace last user message with the enriched contextual version
        if messages and messages[-1]["role"] == "user":
            messages[-1] = {"role": "user", "content": contextual_prompt}
        else:
            messages.append({"role": "user", "content": contextual_prompt})

        # Step 5: Call LLM
        try:
            response = await self._llm.generate(
                system_prompt=SYSTEM_PROMPT,
                messages=messages,
                max_tokens=600,
                temperature=0.4,
            )
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            response = self._fallback_response(intent, conversation.context)

        # Step 6: Save and return
        conversation.add_assistant_message(
            response,
            metadata={"intent": intent.value},
        )
        await self._repo.save(conversation)

        return {
            "conversation_id": conversation.conversation_id,
            "message": response,
            "intent": intent.value,
            "profile_id": conversation.profile_id,
            "has_context": conversation.context.has_data(),
        }

    async def _classify_intent(self, message: str) -> ConversationIntent:
        """Classify user intent.

        Rule-based classifier runs first — it's fast, free, and handles the
        majority of domain-specific messages accurately. Only falls back to
        the LLM when the rule-based result is ambiguous (GENERAL_QUESTION)
        AND the message is short enough that keyword matching is unreliable.
        This eliminates the extra LLM round-trip for ~80% of messages.
        """
        rule_intent = self._rule_based_intent(message)

        # If rule-based gave a specific intent, trust it
        if rule_intent != ConversationIntent.GENERAL_QUESTION:
            logger.debug("Intent (rule-based): %s", rule_intent.value)
            return rule_intent

        # For short ambiguous messages, ask the LLM once
        word_count = len(message.split())
        if word_count <= 25:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)
            try:
                raw = await self._llm.generate(
                    system_prompt="You are a message classifier. Respond with only the category name.",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=20,
                    temperature=0.0,
                )
                intent_str = raw.strip().lower().replace(" ", "_")
                intent = ConversationIntent(intent_str)
                logger.debug("Intent (LLM): %s", intent.value)
                return intent
            except (ValueError, Exception) as exc:
                logger.debug("LLM intent classification failed, using rule-based: %s", exc)

        return rule_intent

    def _rule_based_intent(self, message: str) -> ConversationIntent:
        """Fallback rule-based intent classifier when LLM is unavailable."""
        msg = message.lower()

        keyword_map: dict[str, ConversationIntent] = {
            "loan": ConversationIntent.LOAN_ADVICE,
            "borrow": ConversationIntent.LOAN_ADVICE,
            "credit": ConversationIntent.LOAN_ADVICE,
            "kcc": ConversationIntent.SCHEME_RECOMMENDATION,
            "risk": ConversationIntent.RISK_EXPLANATION,
            "score": ConversationIntent.RISK_EXPLANATION,
            "cash flow": ConversationIntent.CASHFLOW_ANALYSIS,
            "income": ConversationIntent.CASHFLOW_ANALYSIS,
            "expense": ConversationIntent.CASHFLOW_ANALYSIS,
            "season": ConversationIntent.CASHFLOW_ANALYSIS,
            "emi": ConversationIntent.REPAYMENT_PLANNING,
            "repay": ConversationIntent.REPAYMENT_PLANNING,
            "installment": ConversationIntent.REPAYMENT_PLANNING,
            "alert": ConversationIntent.EARLY_WARNING,
            "warn": ConversationIntent.EARLY_WARNING,
            "danger": ConversationIntent.EARLY_WARNING,
            "what if": ConversationIntent.SCENARIO_ANALYSIS,
            "scenario": ConversationIntent.SCENARIO_ANALYSIS,
            "monsoon": ConversationIntent.SCENARIO_ANALYSIS,
            "drought": ConversationIntent.SCENARIO_ANALYSIS,
            "profile": ConversationIntent.PROFILE_SUMMARY,
            "summary": ConversationIntent.PROFILE_SUMMARY,
            "overview": ConversationIntent.PROFILE_SUMMARY,
            "scheme": ConversationIntent.SCHEME_RECOMMENDATION,
            "subsidy": ConversationIntent.SCHEME_RECOMMENDATION,
            "pmfby": ConversationIntent.SCHEME_RECOMMENDATION,
            "government": ConversationIntent.SCHEME_RECOMMENDATION,
            "hello": ConversationIntent.GREETING,
            "hi": ConversationIntent.GREETING,
            "namaste": ConversationIntent.GREETING,
            "thanks": ConversationIntent.GREETING,
            "thank": ConversationIntent.GREETING,
        }

        for keyword, intent in keyword_map.items():
            if keyword in msg:
                return intent

        return ConversationIntent.GENERAL_QUESTION

    def _should_refresh_context(
        self,
        intent: ConversationIntent,
        conversation: Conversation,
    ) -> bool:
        """Decide whether to re-fetch borrower context from services.

        Returns True only when:
        1. No context has been fetched yet, OR
        2. The existing context is older than TTL, OR
        3. The intent needs services not yet present in the cached context.
        """
        ctx = conversation.context

        # No data at all — always fetch
        if not ctx.has_data():
            return True

        # Context is stale (TTL exceeded)
        if ctx.context_fetched_at is not None:
            age = time.time() - ctx.context_fetched_at
            if age > _CONTEXT_TTL_SECONDS:
                logger.debug(
                    "Context stale (%.0fs > %.0fs TTL) — will refresh",
                    age, _CONTEXT_TTL_SECONDS,
                )
                return True

        # Intent needs services that weren't fetched last time
        needed = self._services_for_intent(intent)
        already_fetched = set()
        if ctx.profile_summary is not None:   already_fetched.add("profile")
        if ctx.risk_assessment is not None:   already_fetched.add("risk")
        if ctx.cashflow_forecast is not None: already_fetched.add("cashflow")
        if ctx.loan_exposure is not None:     already_fetched.add("loan")
        if ctx.active_alerts is not None:     already_fetched.add("alert")
        if ctx.active_guidance is not None:   already_fetched.add("guidance")
        missing = needed - already_fetched
        if missing:
            logger.debug("Missing services for intent %s: %s", intent.value, missing)
            return True

        return False

    @staticmethod
    def _services_for_intent(intent: ConversationIntent) -> set[str]:
        """Return the minimal set of services needed for this intent."""
        return INTENT_SERVICES.get(intent.value, {"profile", "risk", "cashflow", "loan"})

    def _build_welcome(self, conversation: Conversation) -> str:
        """Generate a welcome message based on available context."""
        if conversation.context.has_data():
            name = (
                conversation.context.profile_summary or {}
            ).get("name", "")
            greeting = f"Namaste{' ' + name if name else ''}! "
            return (
                f"{greeting}I'm Krishi Mitra, your AI credit advisor. "
                f"I've loaded your financial profile and I'm ready to help. "
                f"You can ask me about loan options, your risk score, "
                f"cash flow patterns, or any questions about managing your finances."
            )
        return (
            "Namaste! I'm Krishi Mitra (कृषि मित्र), your AI credit advisor. "
            "I can help you with loan guidance, risk assessment, "
            "cash flow analysis, and financial planning. "
            "If you share a profile ID, I can provide personalised advice "
            "based on your actual data. How can I help you today?"
        )

    def _fallback_response(
        self,
        intent: ConversationIntent,
        context: BorrowerContext,
    ) -> str:
        """Generate a useful response when the LLM is unavailable."""
        if intent == ConversationIntent.GREETING:
            return self._build_welcome(Conversation(context=context))

        if context.has_data() and context.risk_assessment:
            risk = context.risk_assessment.get("risk_category", "MEDIUM")
            score = context.risk_assessment.get("risk_score", 0)
            return (
                f"Based on your data, your current risk level is {risk} "
                f"(score: {score}/1000). I'm having a brief technical issue "
                f"generating a detailed response right now, but your data is safe. "
                f"Please try again in a moment, or visit your nearest bank branch "
                f"for immediate assistance."
            )

        return (
            "I'm experiencing a brief technical issue and can't generate "
            "a detailed response right now. Please try again in a moment. "
            "For immediate help, you can contact your nearest bank branch "
            "or call the Kisan Call Centre at 1800-180-1551 (toll-free)."
        )

    def _fallback_analysis(self, context: BorrowerContext) -> str:
        """Template-based analysis when LLM is unavailable."""
        if not context.has_data():
            return "No data available for analysis."

        parts = []
        if context.risk_assessment:
            cat = context.risk_assessment.get("risk_category", "UNKNOWN")
            parts.append(f"Risk level: {cat}.")

        if context.loan_exposure:
            dti = context.loan_exposure.get("dti_ratio", 0)
            parts.append(f"Debt-to-income ratio: {dti:.0%}.")

        if context.repayment_capacity:
            emi = context.repayment_capacity.get("recommended_emi", 0)
            parts.append(f"Recommended EMI capacity: Rs {emi:,.0f}.")

        return " ".join(parts) if parts else "Limited data available for analysis."

    def _serialize_conversation(self, conv: Conversation) -> dict[str, Any]:
        """Serialise a Conversation to a dict for API response."""
        return {
            "conversation_id": conv.conversation_id,
            "profile_id": conv.profile_id,
            "language": conv.language,
            "message_count": conv.message_count,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "messages": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata,
                }
                for m in conv.messages
            ],
        }
