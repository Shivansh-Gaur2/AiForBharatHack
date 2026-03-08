"""Amazon Bedrock LLM provider with streaming support.

Supports three model families (auto-detected from model ID):
  - Amazon Nova (``amazon.nova-*`` / ``us.amazon.nova-*``)
  - Anthropic Claude (``anthropic.claude-*`` / ``us.anthropic.claude-*``)
  - Amazon Titan Text (``amazon.titan-text-*``)

Both synchronous ``generate()`` and streaming ``generate_stream()`` are
implemented.  The streaming path uses Bedrock's ``InvokeModelWithResponseStream``
API for real-time token delivery.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class BedrockLLMProvider:
    """LLM provider backed by Amazon Bedrock.

    Implements the ``LLMProvider`` protocol defined in ``domain.interfaces``.
    """

    def __init__(self, model_id: str, region: str = "us-east-1") -> None:
        self._model_id = model_id
        base = model_id.split("/")[-1]
        self._is_claude = "anthropic." in base or "anthropic.claude" in base
        self._is_nova = "amazon.nova" in base
        # Default to Titan if neither
        try:
            self._client = boto3.client("bedrock-runtime", region_name=region)
            logger.info("BedrockLLMProvider initialised (model=%s, region=%s)", model_id, region)
        except Exception as exc:
            logger.warning("Failed to initialise Bedrock client: %s", exc)
            self._client = None

    # ------------------------------------------------------------------
    # Synchronous generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> str:
        """Generate a complete response (non-streaming)."""
        if self._client is None:
            raise RuntimeError("Bedrock client not initialised")

        body = self._build_body(system_prompt, messages, max_tokens, temperature)

        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            response_body = json.loads(response["body"].read())
            text = self._parse_response(response_body)
            if text:
                return text
            raise RuntimeError("Bedrock returned empty response")
        except (BotoCoreError, ClientError) as exc:
            logger.error("Bedrock InvokeModel failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        """Stream response tokens using Bedrock's InvokeModelWithResponseStream."""
        if self._client is None:
            yield "I'm unable to connect to the AI service right now."
            return

        body = self._build_body(system_prompt, messages, max_tokens, temperature)

        try:
            response = self._client.invoke_model_with_response_stream(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            stream = response.get("body")
            if not stream:
                yield "No response stream received."
                return

            for event in stream:
                chunk = event.get("chunk")
                if chunk:
                    chunk_data = json.loads(chunk["bytes"])
                    token = self._parse_stream_chunk(chunk_data)
                    if token:
                        yield token

        except (BotoCoreError, ClientError) as exc:
            logger.error("Bedrock streaming failed: %s", exc)
            yield "I encountered an error while generating the response. Please try again."
        except Exception as exc:
            logger.error("Unexpected streaming error: %s", exc)
            yield "An unexpected error occurred. Please try again."

    # ------------------------------------------------------------------
    # Request body builders
    # ------------------------------------------------------------------

    def _build_body(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> bytes:
        if self._is_claude:
            return self._build_claude_body(system_prompt, messages, max_tokens, temperature)
        elif self._is_nova:
            return self._build_nova_body(system_prompt, messages, max_tokens, temperature)
        else:
            return self._build_titan_body(system_prompt, messages, max_tokens, temperature)

    def _build_claude_body(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> bytes:
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in messages
            ],
        }
        return json.dumps(body).encode()

    def _build_nova_body(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> bytes:
        # Nova uses a messages array with system prompt embedded in first user turn
        nova_messages = []
        for m in messages:
            nova_messages.append({
                "role": m["role"],
                "content": [{"text": m["content"]}],
            })

        # Prepend system context into first user message
        if nova_messages and nova_messages[0]["role"] == "user":
            original_text = nova_messages[0]["content"][0]["text"]
            nova_messages[0]["content"][0]["text"] = (
                f"{system_prompt}\n\n{original_text}"
            )
        else:
            nova_messages.insert(0, {
                "role": "user",
                "content": [{"text": f"{system_prompt}\n\nPlease acknowledge."}],
            })

        body: dict[str, Any] = {
            "messages": nova_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        }
        return json.dumps(body).encode()

    def _build_titan_body(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> bytes:
        # Titan uses a single inputText — concatenate conversation
        parts = [system_prompt, ""]
        for m in messages:
            role = "User" if m["role"] == "user" else "Assistant"
            parts.append(f"{role}: {m['content']}")
        input_text = "\n\n".join(parts)

        body: dict[str, Any] = {
            "inputText": input_text,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        }
        return json.dumps(body).encode()

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    def _parse_response(self, response_body: dict) -> str:
        if self._is_claude:
            content = response_body.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "").strip()
        elif self._is_nova:
            try:
                return response_body["output"]["message"]["content"][0]["text"].strip()
            except (KeyError, IndexError):
                pass
        else:
            # Titan
            results = response_body.get("results", [])
            if results:
                return results[0].get("outputText", "").strip()
        return ""

    def _parse_stream_chunk(self, chunk_data: dict) -> str:
        """Extract text token from a streaming response chunk."""
        if self._is_claude:
            # Claude streaming: delta.text in contentBlockDelta events
            if chunk_data.get("type") == "content_block_delta":
                delta = chunk_data.get("delta", {})
                return delta.get("text", "")
        elif self._is_nova:
            # Nova streaming: contentBlockDelta
            if "contentBlockDelta" in chunk_data:
                delta = chunk_data["contentBlockDelta"].get("delta", {})
                return delta.get("text", "")
        else:
            # Titan streaming
            return chunk_data.get("outputText", "")
        return ""


# ---------------------------------------------------------------------------
# Stub provider for local development without Bedrock
# ---------------------------------------------------------------------------

class StubLLMProvider:
    """Returns canned responses for local development and testing.

    Implements the same ``LLMProvider`` protocol.
    """

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> str:
        return self._generate_stub_response(messages)

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.4,
    ) -> AsyncIterator[str]:
        response = self._generate_stub_response(messages)
        # Simulate streaming by yielding word-by-word
        for word in response.split(" "):
            yield word + " "

    @staticmethod
    def _extract_user_question(content: str) -> str:
        """Extract only the borrower's question from the enriched prompt.

        The contextual prompt built by ``build_contextual_prompt`` appends
        the real user question after ``Borrower's question: ``.  We parse
        that out so keyword matching works on the *actual* user input
        rather than the entire context blob (which always contains words
        like 'loan', 'credit', 'risk', etc.).
        """
        marker = "Borrower's question: "
        idx = content.rfind(marker)
        if idx != -1:
            return content[idx + len(marker):].strip()
        return content.strip()

    def _generate_stub_response(self, messages: list[dict[str, str]]) -> str:
        """Generate contextually relevant stub responses for testing.

        Looks at the full conversation history so follow-up messages like
        "yes", "sure", "tell me more" can reference the previous topic.
        """
        last_content = messages[-1]["content"] if messages else ""
        user_question = self._extract_user_question(last_content)
        msg = user_question.lower()

        # ----- Conversational follow-ups -----
        # If the user sends a short affirmative or continuation, look at the
        # *previous* user turn to determine the topic they want to continue.
        is_followup = len(msg.split()) <= 4 and any(
            w in msg
            for w in [
                "yes", "sure", "ok", "okay", "yeah", "yep", "please",
                "tell me", "go ahead", "continue", "more", "details",
                "elaborate", "explain", "haan", "ha", "ji", "cool",
            ]
        )
        if is_followup:
            # Walk backwards through the conversation to find the last
            # substantive user message with a clear topic
            prev_topic = self._find_previous_topic(messages)
            if prev_topic:
                # Check if we already gave a level-1 follow-up — avoid repeating
                last_assistant = self._last_assistant_content(messages)
                level1 = self._followup_response(prev_topic)
                if last_assistant and last_assistant.strip() == level1.strip():
                    return self._deeper_followup_response(prev_topic)
                return level1

        # ----- Topic-based responses -----
        if any(w in msg for w in ["hello", "hi", "namaste"]):
            return (
                "Namaste! I'm Krishi Mitra, your AI credit advisor. "
                "I can help you with loan guidance, risk assessment, and financial planning. "
                "How can I help you today?"
            )

        if any(w in msg for w in ["cash flow", "cashflow", "income", "expense"]):
            return (
                "Your cash flow follows a seasonal pattern typical of agriculture — "
                "higher income during harvest months (Oct-Dec for Kharif, Mar-Apr for Rabi) "
                "and leaner periods during sowing seasons. Planning loan repayments around "
                "your peak income months can significantly reduce financial stress. "
                "For example, if your main harvest brings in Rs 1,50,000 in November, "
                "you could set aside Rs 40,000-50,000 for upcoming EMI payments."
            )

        if any(w in msg for w in ["loan", "borrow", "credit", "kcc eligib"]):
            return (
                "Based on the available data, I'd recommend considering a loan amount "
                "that keeps your monthly EMI within 40% of your surplus income. "
                "The best time to take a loan is typically after your harvest season "
                "when cash flow is strongest. Would you like me to calculate specific "
                "numbers based on your profile?"
            )

        if any(w in msg for w in ["risk", "score"]):
            return (
                "Your risk assessment considers multiple factors including income stability, "
                "existing debt, repayment history, and external conditions like weather and "
                "market prices. A lower score means lower risk. To improve your risk profile, "
                "consider reducing existing debt and diversifying your income sources."
            )

        if any(w in msg for w in ["scheme", "kcc", "government", "pmfby", "subsid"]):
            return (
                "Several government schemes may benefit you: "
                "1) Kisan Credit Card (KCC) — crop loans at 4% interest with timely repayment. "
                "2) PM Fasal Bima Yojana (PMFBY) — crop insurance at very low premiums. "
                "3) SHG-Bank Linkage — group loans with lower interest rates. "
                "Speak to your nearest bank branch about eligibility."
            )

        if any(w in msg for w in ["what if", "scenario", "monsoon", "drought"]):
            return (
                "That's an important scenario to consider. Weather disruptions can reduce "
                "crop yields by 20-50%, which directly impacts your repayment capacity. "
                "I'd recommend maintaining an emergency fund of at least 3 months' expenses "
                "and considering crop insurance under PMFBY before taking on new debt."
            )

        if any(w in msg for w in ["emi", "repay", "installment"]):
            return (
                "When planning your repayments, align your EMI due dates with your "
                "harvest income cycle. For most farmers, post-harvest months are the "
                "best time for larger payments. If possible, opt for a flexible "
                "repayment plan that allows smaller EMIs during lean months and "
                "larger ones after harvest. Your bank may offer seasonal repayment "
                "options under KCC."
            )

        if any(w in msg for w in ["alert", "warn", "danger"]):
            return (
                "Early warnings help you prepare before problems escalate. "
                "Key signals to watch: declining soil moisture, delayed monsoon forecasts, "
                "rising input costs, or an EMI-to-income ratio crossing 50%. "
                "If any alerts are active on your profile, I'd recommend discussing "
                "restructuring options with your bank proactively."
            )

        if any(w in msg for w in ["profile", "summary", "overview"]):
            return (
                "Your profile summarises key financial indicators: income sources, "
                "existing debt, repayment history, risk category, and cash-flow patterns. "
                "Keeping your profile data up-to-date helps generate more accurate advice. "
                "Would you like me to walk through each section?"
            )

        return (
            "That's a great question about rural finance. Based on best practices, "
            "I'd suggest focusing on building a strong repayment track record, "
            "diversifying your income sources where possible, and timing your borrowing "
            "to align with your seasonal income patterns. Would you like specific advice "
            "on any of these areas?"
        )

    @staticmethod
    def _last_assistant_content(messages: list[dict[str, str]]) -> str | None:
        """Return the content of the most recent assistant message."""
        for m in reversed(messages):
            if m["role"] == "assistant":
                return m["content"]
        return None

    def _find_previous_topic(self, messages: list[dict[str, str]]) -> str | None:
        """Scan earlier user messages for a substantive topic.

        Returns the lowered user-question text of the most recent user
        turn that contained a recognisable topic keyword, or ``None``.
        """
        topic_keywords = [
            "loan", "borrow", "credit", "risk", "score", "cash flow",
            "cashflow", "income", "expense", "scheme", "kcc", "government",
            "pmfby", "what if", "scenario", "monsoon", "drought",
            "emi", "repay", "installment", "alert", "warn", "profile",
            "summary", "overview", "hello", "hi", "namaste",
        ]
        # Walk from second-to-last backwards (skip final user message)
        for m in reversed(messages[:-1]):
            if m["role"] != "user":
                continue
            question = self._extract_user_question(m["content"]).lower()
            if any(kw in question for kw in topic_keywords):
                return question
        return None

    def _followup_response(self, prev_topic: str) -> str:
        """Generate a continuation response when the user says 'yes' / 'tell me more'.

        These are deliberately different from the initial topic responses so
        the conversation doesn't feel like a broken record.
        """
        if any(w in prev_topic for w in ["cash flow", "cashflow", "income", "expense"]):
            return (
                "Here are the specifics based on your profile:\n\n"
                "- **Peak income months**: Typically Oct-Dec (Kharif harvest) and Mar-Apr (Rabi harvest).\n"
                "- **Lean months**: Jun-Aug (sowing season) when expenses are high but revenue is low.\n"
                "- **Recommendation**: Try to keep at least Rs 15,000-20,000 as a buffer during lean months. "
                "If you're planning a loan, schedule EMI payments in Nov or Apr when surplus is highest.\n\n"
                "Would you like me to look at a specific month or compare seasons?"
            )

        if any(w in prev_topic for w in ["loan", "borrow", "credit"]):
            return (
                "Let me break it down with approximate numbers:\n\n"
                "- **Safe EMI range**: Up to 40% of your monthly surplus income.\n"
                "- **Best timing**: Apply after your main harvest when bank statements show healthy inflows.\n"
                "- **KCC option**: If you have 2+ acres, Kisan Credit Card offers crop loans at just 4% p.a. "
                "(with timely repayment subvention).\n"
                "- **Tip**: A good repayment track record on a small loan first can help you "
                "qualify for larger amounts later.\n\n"
                "Would you like me to estimate a specific loan amount based on your income?"
            )

        if any(w in prev_topic for w in ["risk", "score"]):
            return (
                "Let me explain the key factors affecting your risk score:\n\n"
                "1. **Income stability** — Regular, predictable income lowers risk.\n"
                "2. **Existing debt burden** — High debt-to-income ratio increases risk.\n"
                "3. **Repayment history** — On-time payments significantly improve your score.\n"
                "4. **External factors** — Weather, market prices, and crop choice also matter.\n\n"
                "To improve: focus on clearing small dues first, diversify crops if possible, "
                "and consider crop insurance under PMFBY. Shall I suggest specific steps for your situation?"
            )

        if any(w in prev_topic for w in ["scheme", "kcc", "government", "pmfby", "subsid"]):
            return (
                "Here are more details on the top schemes relevant to you:\n\n"
                "**Kisan Credit Card (KCC)**:\n"
                "- Crop loan up to Rs 3 lakh at 4% interest (with subvention)\n"
                "- Apply at any commercial or cooperative bank with land records\n\n"
                "**PM Fasal Bima Yojana (PMFBY)**:\n"
                "- Crop insurance: 2% premium for Kharif, 1.5% for Rabi\n"
                "- Covers yield loss due to weather, pests, and natural calamities\n\n"
                "**PM-KISAN**:\n"
                "- Rs 6,000/year direct benefit transfer in 3 installments\n\n"
                "Would you like help checking your eligibility for any of these?"
            )

        if any(w in prev_topic for w in ["what if", "scenario", "monsoon", "drought"]):
            return (
                "Let me model the scenario in more detail:\n\n"
                "- **Delayed monsoon (2-3 weeks)**: Likely 15-25% crop yield reduction. "
                "Your repayment capacity could drop proportionally.\n"
                "- **Severe drought**: Yield loss of 40-60%. Crop insurance payout "
                "(if enrolled) typically arrives within 2-3 months.\n"
                "- **Mitigation**: Maintain an emergency fund, stagger crop planting, "
                "and explore drip irrigation for water efficiency.\n\n"
                "Would you like me to estimate the financial impact on your specific loans?"
            )

        if any(w in prev_topic for w in ["emi", "repay", "installment"]):
            return (
                "Here's a practical repayment plan approach:\n\n"
                "- **Harvest months (high income)**: Pay 150-200% of your regular EMI to reduce principal faster.\n"
                "- **Lean months**: Pay the minimum required EMI amount.\n"
                "- **Annual lump sum**: If you receive PM-KISAN or insurance payouts, "
                "consider putting a portion towards loan prepayment.\n\n"
                "This 'seasonal EMI' strategy can save you Rs 5,000-10,000 in interest over a year. "
                "Shall I calculate exact amounts based on a specific loan?"
            )

        # Generic follow-up
        return (
            "Sure! Based on your profile data, here's a more detailed breakdown. "
            "Your financial position is influenced by seasonal income patterns, "
            "existing obligations, and local market conditions. "
            "I'd recommend reviewing your profile dashboard for the latest numbers, "
            "and I'm happy to dive deeper into any specific aspect — just ask!"
        )

    def _deeper_followup_response(self, prev_topic: str) -> str:
        """Third-level response when the user keeps confirming after a follow-up.

        Prevents the bot from repeating the same follow-up verbatim.
        """
        if any(w in prev_topic for w in ["cash flow", "cashflow", "income", "expense"]):
            return (
                "Great! Let me give you actionable next steps:\n\n"
                "1. Track your daily expenses for one month using a simple notebook or phone app.\n"
                "2. Set aside 10-15% of every harvest payment into a savings account before spending.\n"
                "3. If you have a KCC, use the overdraft facility only during sowing season — repay fully after harvest.\n"
                "4. Consider a recurring deposit of Rs 2,000-3,000/month during peak months.\n\n"
                "These small habits can improve your cash flow stability significantly. "
                "Anything else you'd like to know?"
            )

        if any(w in prev_topic for w in ["loan", "borrow", "credit"]):
            return (
                "Here's a step-by-step action plan for your loan application:\n\n"
                "1. Gather documents: land records (7/12 extract), Aadhaar, last 6 months bank statement.\n"
                "2. Check your existing debt — ideally total EMIs should be under 40% of monthly income.\n"
                "3. Visit your nearest branch and ask specifically about KCC or crop loan products.\n"
                "4. If applying for the first time, start with a smaller amount (Rs 50,000-1,00,000) to build history.\n\n"
                "A good repayment record on this first loan will help you access larger credit next season. "
                "Would you like to explore a different topic?"
            )

        if any(w in prev_topic for w in ["risk", "score"]):
            return (
                "Here are concrete steps to lower your risk over the next 3-6 months:\n\n"
                "1. Clear any overdue payments — even small amounts matter for your credit record.\n"
                "2. Register for PMFBY crop insurance this season (premium is just 2% for Kharif).\n"
                "3. If you have multiple loans, consider consolidating them into one KCC account.\n"
                "4. Diversify: even a small secondary income (dairy, poultry, kitchen garden) reduces risk.\n\n"
                "These steps can meaningfully improve your risk category within one crop cycle. "
                "Is there anything else I can help with?"
            )

        if any(w in prev_topic for w in ["scheme", "kcc", "government", "pmfby", "subsid"]):
            return (
                "To apply for these schemes, here's what to do:\n\n"
                "For KCC: Visit your bank with land documents + Aadhaar + passport photo. "
                "Processing takes 7-15 days. The credit limit is set based on your crop and area.\n\n"
                "For PMFBY: Enrollment is automatic if you have a crop loan. Otherwise, "
                "visit any bank or Common Service Centre (CSC) with land records before the cutoff date.\n\n"
                "For PM-KISAN: Register at pmkisan.gov.in or visit your local agriculture office. "
                "Benefits are credited directly to your bank account.\n\n"
                "Need help with anything else?"
            )

        return (
            "I appreciate your interest! At this point, I'd recommend:\n\n"
            "1. Reviewing your profile dashboard for the latest numbers.\n"
            "2. Visiting your nearest bank branch with your documents for personalised advice.\n"
            "3. Calling the Kisan Call Centre at 1800-180-1551 (toll-free) for any scheme-related queries.\n\n"
            "I'm here if you want to explore a new topic — just ask!"
        )
