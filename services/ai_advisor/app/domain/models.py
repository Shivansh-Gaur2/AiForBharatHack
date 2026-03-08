"""Domain models for the AI Advisor service.

Pure data structures with no framework dependencies.  These represent
the conversation state, individual messages, and the aggregated context
that the LLM needs to generate informed responses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
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

    def has_data(self) -> bool:
        """Return True if at least some data has been fetched."""
        return any([
            self.profile_summary,
            self.risk_assessment,
            self.cashflow_forecast,
            self.loan_exposure,
            self.active_loans,
            self.active_alerts,
            self.active_guidance,
        ])

    def to_prompt_context(self) -> str:
        """Serialise available data into a compact text block for LLM context."""
        sections: list[str] = []

        if self.profile_summary:
            p = self.profile_summary
            sections.append(
                f"BORROWER PROFILE:\n"
                f"  Name: {p.get('name', 'N/A')}\n"
                f"  Occupation: {p.get('occupation', 'N/A')}\n"
                f"  Region/State: {p.get('region', 'N/A')}\n"
                f"  Land holding: {p.get('land_holding_acres', 'N/A')} acres\n"
                f"  Household size: {p.get('household_size', 'N/A')}\n"
                f"  Monthly income (avg): Rs {p.get('avg_monthly_income', 0):,.0f}\n"
                f"  Monthly expense (avg): Rs {p.get('avg_monthly_expense', 0):,.0f}\n"
                f"  Crops: {', '.join(p.get('crops', [])) or 'N/A'}\n"
                f"  Livestock: {p.get('livestock_summary', 'None')}"
            )

        if self.risk_assessment:
            r = self.risk_assessment
            sections.append(
                f"RISK ASSESSMENT:\n"
                f"  Risk score: {r.get('risk_score', 'N/A')}/1000\n"
                f"  Risk category: {r.get('risk_category', 'N/A')}\n"
                f"  Key risk factors: {', '.join(f.get('name', '') for f in r.get('risk_factors', []))}\n"
                f"  Confidence: {r.get('confidence_level', 'N/A')}"
            )

        if self.cashflow_forecast:
            cf = self.cashflow_forecast
            sections.append(
                f"CASH FLOW FORECAST:\n"
                f"  Forecast period: {cf.get('period', 'N/A')}\n"
                f"  Avg monthly inflow: Rs {cf.get('avg_inflow', 0):,.0f}\n"
                f"  Avg monthly outflow: Rs {cf.get('avg_outflow', 0):,.0f}\n"
                f"  Peak income months: {cf.get('peak_months', 'N/A')}\n"
                f"  Lean months: {cf.get('lean_months', 'N/A')}"
            )

        if self.repayment_capacity:
            rc = self.repayment_capacity
            sections.append(
                f"REPAYMENT CAPACITY:\n"
                f"  Recommended EMI: Rs {rc.get('recommended_emi', 0):,.0f}\n"
                f"  Max affordable EMI: Rs {rc.get('max_affordable_emi', rc.get('max_emi', 0)):,.0f}\n"
                f"  Monthly surplus (avg): Rs {rc.get('monthly_surplus_avg', 0):,.0f}\n"
                f"  Monthly surplus (min): Rs {rc.get('monthly_surplus_min', 0):,.0f}\n"
                f"  Annual repayment capacity: Rs {rc.get('annual_repayment_capacity', 0):,.0f}\n"
                f"  DSCR: {rc.get('debt_service_coverage_ratio', rc.get('dscr', 'N/A'))}\n"
                f"  Emergency reserve: Rs {rc.get('emergency_reserve', 0):,.0f}"
            )

        if self.active_loans:
            loan_lines = []
            total_outstanding = 0.0
            for loan in self.active_loans:
                principal = loan.get('principal', 0)
                outstanding = loan.get('outstanding_balance', principal)
                total_outstanding += outstanding
                lender = loan.get('lender_name', 'Unknown')
                source = loan.get('source_type', '')
                status = loan.get('status', 'ACTIVE')
                loan_lines.append(
                    f"  - {lender} ({source}): Principal Rs {principal:,.0f}, "
                    f"Outstanding Rs {outstanding:,.0f}, Status: {status}"
                )
            sections.append(
                f"ACTIVE LOANS ({len(self.active_loans)} total, "
                f"Total Outstanding: Rs {total_outstanding:,.0f}):\n"
                + "\n".join(loan_lines)
            )

        if self.loan_exposure:
            le = self.loan_exposure
            dti = le.get('dti_ratio', 0)
            dti_str = f"{dti:.1%}" if isinstance(dti, (int, float)) else str(dti)
            sections.append(
                f"DEBT EXPOSURE SUMMARY:\n"
                f"  Total outstanding: Rs {le.get('total_outstanding', 0):,.0f}\n"
                f"  Monthly obligations: Rs {le.get('monthly_obligations', 0):,.0f}\n"
                f"  Debt-to-income ratio: {dti_str}\n"
                f"  Active loans: {le.get('active_loan_count', 0)}\n"
                f"  Loan sources: {', '.join(s.get('source_type', '') for s in le.get('sources', []))}"
            )

        if self.active_alerts:
            alert_lines = []
            for a in self.active_alerts[:5]:
                alert_lines.append(
                    f"  - [{a.get('severity', 'INFO')}] {a.get('alert_type', '')}: "
                    f"{a.get('message', 'No details')}"
                )
            sections.append(f"ACTIVE ALERTS:\n" + "\n".join(alert_lines))

        if self.active_guidance:
            g = self.active_guidance[0] if self.active_guidance else {}
            sections.append(
                f"LATEST GUIDANCE:\n"
                f"  Recommended amount: Rs {g.get('min_amount', 0):,.0f} – Rs {g.get('max_amount', 0):,.0f}\n"
                f"  Optimal timing: {g.get('timing', 'N/A')}\n"
                f"  Suggested tenure: {g.get('tenure_months', 'N/A')} months\n"
                f"  AI summary: {g.get('ai_summary', 'N/A')}"
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

    def get_message_history(self, max_messages: int = 20) -> list[dict[str, str]]:
        """Return recent messages formatted for LLM consumption."""
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [
            {"role": m.role.value, "content": m.content}
            for m in recent
            if m.role != MessageRole.SYSTEM
        ]

    @property
    def message_count(self) -> int:
        return len(self.messages)
