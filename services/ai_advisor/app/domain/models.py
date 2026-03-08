"""Domain models for the AI Advisor service.

Pure data structures with no framework dependencies.  These represent
the conversation state, individual messages, and the aggregated context
that the LLM needs to generate informed responses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from services.shared.models import ProfileId, generate_id


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationIntent(str, Enum):
    """High-level intent categories the advisor can handle."""
    GENERAL_QUESTION = "general_question"
    LOAN_ADVICE = "loan_advice"
    RISK_EXPLANATION = "risk_explanation"
    CASHFLOW_ANALYSIS = "cashflow_analysis"
    REPAYMENT_PLANNING = "repayment_planning"
    EARLY_WARNING = "early_warning"
    SCENARIO_ANALYSIS = "scenario_analysis"
    PROFILE_SUMMARY = "profile_summary"
    SCHEME_RECOMMENDATION = "scheme_recommendation"
    GREETING = "greeting"


class AdvisorTool(str, Enum):
    """Tools the AI advisor can invoke to gather data."""
    FETCH_PROFILE = "fetch_profile"
    FETCH_RISK = "fetch_risk"
    FETCH_CASHFLOW = "fetch_cashflow"
    FETCH_LOANS = "fetch_loans"
    FETCH_ALERTS = "fetch_alerts"
    FETCH_GUIDANCE = "fetch_guidance"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Result of invoking a data-fetching tool."""
    tool: AdvisorTool
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Aggregated Context
# ---------------------------------------------------------------------------

@dataclass
class BorrowerContext:
    """Aggregated borrower context assembled from all micro-services.

    This is the 'knowledge base' the LLM prompt is built from.
    """
    profile_id: ProfileId | None = None

    # Profile service data
    profile_summary: dict[str, Any] | None = None

    # Risk service data
    risk_assessment: dict[str, Any] | None = None

    # Cash-flow service data
    cashflow_forecast: dict[str, Any] | None = None
    repayment_capacity: dict[str, Any] | None = None

    # Loan tracker data
    loan_exposure: dict[str, Any] | None = None
    active_loans: list[dict[str, Any]] = field(default_factory=list)

    # Early-warning data
    active_alerts: list[dict[str, Any]] = field(default_factory=list)

    # Guidance data
    active_guidance: list[dict[str, Any]] = field(default_factory=list)

    # Metadata — populated by the aggregator
    context_fetched_at: float | None = None          # epoch seconds when context was last fetched
    unavailable_services: list[str] = field(default_factory=list)  # services that failed/timed out

    def has_data(self) -> bool:
        """Return True if at least some data has been fetched."""
        return any([
            self.profile_summary,
            self.risk_assessment,
            self.cashflow_forecast,
            self.loan_exposure,
            self.active_alerts,
            self.active_guidance,
        ])

    def to_prompt_context(self) -> str:
        """Serialise available data into a compact text block for LLM context."""
        sections: list[str] = []

        # Freshness header so the LLM doesn't present stale data as current
        if self.context_fetched_at:
            fetched_dt = datetime.fromtimestamp(self.context_fetched_at, tz=UTC)
            sections.append(
                f"[Data fetched: {fetched_dt.strftime('%d %b %Y %H:%M')} UTC]"
            )

        if self.profile_summary:
            p = self.profile_summary
            secondary = p.get("secondary_occupations", [])
            sec_str = f" + {', '.join(secondary)}" if secondary else ""
            sections.append(
                f"BORROWER PROFILE:\n"
                f"  Name: {p.get('name', 'N/A')}\n"
                f"  Age: {p.get('age', 'N/A')}\n"
                f"  Occupation: {p.get('occupation', 'N/A')}{sec_str}\n"
                f"  Region/State: {p.get('region', 'N/A')}\n"
                f"  Land holding: {p.get('land_holding_acres', 'N/A')} acres ({p.get('land_type', 'N/A')})\n"
                f"  Household size: {p.get('household_size', 'N/A')} (dependents: {p.get('dependents', 'N/A')})\n"
                f"  Monthly income (avg last 12 months): Rs {p.get('avg_monthly_income', 0):,.0f}\n"
                f"  Monthly expense (avg last 12 months): Rs {p.get('avg_monthly_expense', 0):,.0f}\n"
                f"  Crops: {', '.join(p.get('crops', [])) or 'N/A'}\n"
                f"  Livestock: {p.get('livestock_summary', 'None')}"
            )

        if self.risk_assessment:
            r = self.risk_assessment
            factors = ", ".join(f.get("name", "") for f in r.get("risk_factors", []))
            sections.append(
                f"RISK ASSESSMENT:\n"
                f"  Risk score: {r.get('risk_score', 'N/A')}/1000\n"
                f"  Risk category: {r.get('risk_category', 'N/A')}\n"
                f"  Key risk factors: {factors or 'N/A'}\n"
                f"  Confidence: {r.get('confidence_level', 'N/A')}"
            )

        if self.cashflow_forecast:
            cf = self.cashflow_forecast
            sections.append(
                f"CASH FLOW FORECAST:\n"
                f"  Forecast period: {cf.get('period', 'N/A')}\n"
                f"  Avg monthly inflow: Rs {cf.get('avg_inflow', 0):,.0f}\n"
                f"  Avg monthly outflow: Rs {cf.get('avg_outflow', 0):,.0f}\n"
                f"  Avg monthly surplus: Rs {cf.get('avg_inflow', 0) - cf.get('avg_outflow', 0):,.0f}\n"
                f"  Peak income months: {cf.get('peak_months', 'N/A')}\n"
                f"  Lean months: {cf.get('lean_months', 'N/A')}"
            )

        if self.repayment_capacity:
            rc = self.repayment_capacity
            sections.append(
                f"REPAYMENT CAPACITY:\n"
                f"  Recommended EMI: Rs {rc.get('recommended_emi', 0):,.0f}\n"
                f"  Max EMI: Rs {rc.get('max_emi', 0):,.0f}\n"
                f"  DSCR: {rc.get('dscr', 'N/A')}\n"
                f"  Emergency reserve: Rs {rc.get('emergency_reserve', 0):,.0f}"
            )

        if self.loan_exposure:
            le = self.loan_exposure
            sources = ", ".join(s.get("source_type", "") for s in le.get("sources", []))
            sections.append(
                f"DEBT EXPOSURE:\n"
                f"  Total outstanding: Rs {le.get('total_outstanding', 0):,.0f}\n"
                f"  Monthly obligations: Rs {le.get('monthly_obligations', 0):,.0f}\n"
                f"  Debt-to-income ratio: {le.get('dti_ratio', 0):.1%}\n"
                f"  Active loans: {le.get('active_loan_count', 0)}\n"
                f"  Loan sources: {sources or 'N/A'}"
            )

        # Individual loan details — critical for specific advice (Bug 2 fix)
        if self.active_loans:
            loan_lines = []
            for i, loan in enumerate(self.active_loans[:5], 1):
                lender = loan.get("lender", loan.get("lender_name", "Unknown"))
                outstanding = loan.get("outstanding_balance", loan.get("current_balance", 0))
                emi = loan.get("monthly_emi", loan.get("emi_amount", 0))
                purpose = loan.get("loan_purpose", loan.get("purpose", ""))
                next_due = loan.get("next_due_date", "")
                loan_lines.append(
                    f"  {i}. {lender}: Rs {outstanding:,.0f} outstanding"
                    + (f", EMI Rs {emi:,.0f}/mo" if emi else "")
                    + (f", purpose: {purpose}" if purpose else "")
                    + (f", next due: {next_due}" if next_due else "")
                )
            sections.append("ACTIVE LOAN DETAILS:\n" + "\n".join(loan_lines))

        if self.active_alerts:
            alert_lines = []
            for a in self.active_alerts[:5]:
                alert_lines.append(
                    f"  - [{a.get('severity', 'INFO')}] {a.get('alert_type', '')}: "
                    f"{a.get('message', 'No details')}"
                )
            sections.append("ACTIVE ALERTS:\n" + "\n".join(alert_lines))

        # All active guidance records (up to 3), not just index 0 (Bug 6 fix)
        if self.active_guidance:
            guidance_lines = []
            for i, g in enumerate(self.active_guidance[:3], 1):
                guidance_lines.append(
                    f"  {i}. Recommended amount: Rs {g.get('min_amount', 0):,.0f}"
                    f" – Rs {g.get('max_amount', 0):,.0f}\n"
                    f"     Timing: {g.get('timing', 'N/A')} | "
                    f"Tenure: {g.get('tenure_months', 'N/A')} months\n"
                    f"     Summary: {g.get('ai_summary', g.get('summary', 'N/A'))}"
                )
            sections.append("ACTIVE GUIDANCE:\n" + "\n\n".join(guidance_lines))

        # Surface which services were unavailable so the LLM can be transparent (Improvement 6)
        if self.unavailable_services:
            names = ", ".join(self.unavailable_services)
            sections.append(
                f"DATA GAPS (services currently unreachable): {names}\n"
                f"  Note: Let the user know specific data for these areas is temporarily unavailable."
            )

        if not sections:
            return "No borrower data available. Provide general rural credit guidance."

        return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Conversation Aggregate
# ---------------------------------------------------------------------------

@dataclass
class Conversation:
    """Root aggregate for an AI advisor conversation session."""
    conversation_id: str = field(default_factory=lambda: generate_id("conv"))
    profile_id: ProfileId | None = None
    messages: list[Message] = field(default_factory=list)
    context: BorrowerContext = field(default_factory=BorrowerContext)
    language: str = "en"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_user_message(self, content: str) -> Message:
        msg = Message(role=MessageRole.USER, content=content)
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_assistant_message(self, content: str, metadata: dict[str, Any] | None = None) -> Message:
        msg = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def get_message_history(self, max_chars: int = 12_000) -> list[dict[str, str]]:
        """Return recent messages formatted for LLM consumption.

        Uses a character budget rather than a fixed message count to prevent
        context window overflow when the injected borrower-context block is large.
        Token estimate: ~4 chars / token, so 12 000 chars ≈ 3 000 tokens for history.
        """
        all_msgs = [
            {"role": m.role.value, "content": m.content}
            for m in self.messages
            if m.role != MessageRole.SYSTEM
        ]
        # Walk from newest → oldest, accumulate until budget exceeded
        budget = max_chars
        selected: list[dict[str, str]] = []
        for msg in reversed(all_msgs):
            cost = len(msg["content"]) + 20  # ~20 chars overhead per message
            if budget - cost < 0 and selected:
                break  # keep at least 1 message even if it exceeds budget
            budget -= cost
            selected.append(msg)
        selected.reverse()
        return selected

    @property
    def message_count(self) -> int:
        return len(self.messages)


# ---------------------------------------------------------------------------
# Intent → required services mapping (domain knowledge, not infrastructure)
# ---------------------------------------------------------------------------

#: Maps a ConversationIntent value to the minimal set of service names
#: that need to be fetched to answer that intent adequately.
INTENT_SERVICES: dict[str, set[str]] = {
    "greeting":              set(),
    "general_question":      {"profile"},
    "loan_advice":           {"profile", "risk", "cashflow", "loan", "guidance"},
    "risk_explanation":      {"profile", "risk"},
    "cashflow_analysis":     {"profile", "cashflow"},
    "repayment_planning":    {"profile", "cashflow", "loan"},
    "early_warning":         {"profile", "risk", "alert"},
    "scenario_analysis":     {"profile", "risk", "cashflow", "loan"},
    "profile_summary":       {"profile", "risk", "loan"},
    "scheme_recommendation": {"profile", "risk"},
}
