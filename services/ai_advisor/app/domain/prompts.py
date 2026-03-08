"""Prompt templates for the AI Advisor.

Centralised prompt management following the single-responsibility principle.
Each prompt template is a pure function that takes structured context and
returns a formatted string — no side effects, easily testable.
"""

from __future__ import annotations

from .models import BorrowerContext, ConversationIntent


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are **Krishi Mitra** (कृषि मित्र), an AI-powered rural credit advisor \
for small farmers, SHG members, tenant farmers, and seasonal migrants in India.

## Your Role
- Provide clear, actionable financial guidance in simple language.
- Help borrowers understand their loan options, risk exposure, and repayment capacity.
- Align credit recommendations with seasonal agricultural cycles and livelihood patterns.
- Proactively warn about potential repayment difficulties.
- Recommend government schemes (KCC, PMFBY, SHG loans) when applicable.

## Communication Guidelines
- Use simple, jargon-free language a farmer with limited formal education can understand.
- Use relatable examples (e.g., "Your monthly EMI would be about the cost of 2 bags of DAP fertiliser").
- Be empathetic and encouraging — never judgemental about debt or financial difficulties.
- If the borrower's risk is HIGH or VERY_HIGH, express concern gently and suggest protective steps.
- When data is available, ground your advice in the actual numbers — cite specific amounts.
- If you don't have enough data to give specific advice, say so honestly and suggest what information would help.

## Response Format
- Keep responses concise: 3–6 sentences for simple questions, up to 2 short paragraphs for complex analysis.
- Use bullet points only when listing specific action items or comparing options.
- Always end actionable advice with a clear next step the borrower can take.
- When discussing money, use Rs (₹) with Indian number formatting.

## Safety Rules
- Never guarantee loan approval or specific interest rates — you provide guidance, not decisions.
- Never ask for passwords, Aadhaar numbers, or bank account details.
- If asked about topics outside rural credit and finance, politely redirect.
- Always recommend consulting a bank officer or credit counsellor for final decisions.
"""


# ---------------------------------------------------------------------------
# Intent Classification Prompt
# ---------------------------------------------------------------------------

INTENT_CLASSIFICATION_PROMPT = """\
Classify the user's message into exactly one of these categories:
- general_question: General questions about loans, credit, farming finance
- loan_advice: Asking about taking a new loan, loan amounts, timing
- risk_explanation: Asking about their risk score, why risk is high/low
- cashflow_analysis: Questions about income, expenses, seasonal patterns
- repayment_planning: Questions about EMI, repayment schedule, capacity
- early_warning: Questions about alerts, potential problems, risk warnings
- scenario_analysis: What-if questions (e.g., "what if monsoon fails?")
- profile_summary: Asking about their own profile or financial summary
- scheme_recommendation: Asking about government schemes, subsidies, KCC
- greeting: Simple hello, thanks, goodbye

Respond with ONLY the category name, nothing else.

User message: {message}
"""


# ---------------------------------------------------------------------------
# Contextual Response Prompt Builder
# ---------------------------------------------------------------------------

def build_contextual_prompt(
    user_message: str,
    context: BorrowerContext,
    intent: ConversationIntent,
    language: str = "en",
) -> str:
    """Build a user prompt enriched with borrower context.

    The system prompt is sent separately; this builds the *user-turn* content
    that includes the data context and the actual question.
    """
    parts: list[str] = []

    # Inject borrower context if available
    context_text = context.to_prompt_context()
    if context.has_data():
        parts.append(
            "Here is the borrower's current financial data from our system:\n\n"
            f"{context_text}\n\n"
            "---\n"
        )

    # Intent-specific guidance injected into the user turn
    intent_guidance = _INTENT_GUIDANCE.get(intent, "")
    if intent_guidance:
        parts.append(f"[Advisor focus: {intent_guidance}]\n\n")

    # Language instruction
    if language != "en":
        lang_name = _LANGUAGE_MAP.get(language, language)
        parts.append(
            f"IMPORTANT: Respond in {lang_name}. Use the local script. "
            f"You may use common English financial terms (EMI, loan, interest) "
            f"if they are widely understood.\n\n"
        )

    parts.append(f"Borrower's question: {user_message}")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Quick-Analysis Prompt (for dashboard insights)
# ---------------------------------------------------------------------------

def build_quick_analysis_prompt(context: BorrowerContext) -> str:
    """Build a prompt for generating a quick borrower analysis summary.

    Used by the dashboard to show an AI-powered insight card.
    """
    context_text = context.to_prompt_context()
    return (
        "Based on the following borrower data, provide a brief 3-4 sentence "
        "financial health summary. Highlight the most important insight "
        "(positive or concerning) and suggest ONE actionable next step.\n\n"
        f"{context_text}"
    )


# ---------------------------------------------------------------------------
# Scenario Analysis Prompt
# ---------------------------------------------------------------------------

def build_scenario_prompt(
    context: BorrowerContext,
    scenario_description: str,
) -> str:
    """Build a prompt for AI-powered scenario analysis."""
    context_text = context.to_prompt_context()
    return (
        "The borrower wants to understand what would happen in this scenario:\n"
        f'"{scenario_description}"\n\n'
        f"Here is their current financial data:\n\n{context_text}\n\n"
        "Analyse the likely impact on their repayment capacity, income, and risk level. "
        "Be specific with estimated numbers where possible. "
        "End with 2-3 concrete steps they can take to protect themselves."
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

_INTENT_GUIDANCE: dict[ConversationIntent, str] = {
    ConversationIntent.LOAN_ADVICE: (
        "Focus on loan amount recommendations, optimal timing based on crop cycles, "
        "interest rate comparisons between formal/informal sources, and repayment feasibility."
    ),
    ConversationIntent.RISK_EXPLANATION: (
        "Explain the risk score and factors in simple terms. "
        "Use analogies the borrower can relate to. Suggest concrete steps to reduce risk."
    ),
    ConversationIntent.CASHFLOW_ANALYSIS: (
        "Focus on seasonal income/expense patterns, peak and lean months, "
        "and how cash flow affects borrowing decisions."
    ),
    ConversationIntent.REPAYMENT_PLANNING: (
        "Focus on EMI calculations, repayment schedules, and capacity analysis. "
        "Warn about months where repayment may be difficult."
    ),
    ConversationIntent.EARLY_WARNING: (
        "Address active alerts and potential repayment stress. "
        "Be empathetic but clear about risks. Suggest immediate protective actions."
    ),
    ConversationIntent.SCENARIO_ANALYSIS: (
        "Model the what-if scenario against the borrower's actual data. "
        "Be realistic about potential impacts but also highlight coping strategies."
    ),
    ConversationIntent.PROFILE_SUMMARY: (
        "Provide a holistic overview of the borrower's financial position. "
        "Highlight strengths and areas of concern."
    ),
    ConversationIntent.SCHEME_RECOMMENDATION: (
        "Recommend relevant government schemes: Kisan Credit Card (KCC), "
        "PM Fasal Bima Yojana (PMFBY), SHG-Bank Linkage, MUDRA loans, "
        "and any state-specific schemes. Explain eligibility and benefits simply."
    ),
    ConversationIntent.GENERAL_QUESTION: (
        "Provide helpful general information about rural credit and farming finance."
    ),
    ConversationIntent.GREETING: (
        "Respond warmly and briefly. If a profile is loaded, mention you have "
        "their data ready. Offer to help with loans, risk, or financial planning."
    ),
}

_LANGUAGE_MAP: dict[str, str] = {
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "mr": "Marathi (मराठी)",
    "bn": "Bengali (বাংলা)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "en": "English",
}
