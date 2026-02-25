"""English message catalog — serves as the canonical reference for all keys.

Categories:
- risk.*          Risk assessment messages
- guidance.*      Credit guidance messages
- alert.*         Early warning messages
- consent.*       Privacy & consent messages
- loan.*          Loan tracking messages
- general.*       Common UI messages
- cultural.*      Culturally appropriate financial examples
"""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # ===================================================================
    # Risk Assessment
    # ===================================================================
    "risk.category.low": "Low Risk",
    "risk.category.medium": "Medium Risk",
    "risk.category.high": "High Risk",
    "risk.category.very_high": "Very High Risk",
    "risk.score_explanation": "Your risk score is {score} out of 1000. A lower score means lower risk.",
    "risk.dti_ratio": "Your debt-to-income ratio is {ratio:.0%}. This means {ratio:.0%} of your income goes to loan repayments.",
    "risk.factor.high_dti": "Your loan repayments are a large portion of your income",
    "risk.factor.informal_loans": "You have loans from informal sources with high interest rates",
    "risk.factor.seasonal_income": "Your income varies significantly across seasons",
    "risk.factor.weather_dependent": "Your income depends on weather conditions",
    "risk.factor.single_crop": "Your income comes from a single crop",
    "risk.factor.no_insurance": "You do not have crop or livestock insurance",
    "risk.improvement.diversify": "Consider diversifying your income sources",
    "risk.improvement.insurance": "Consider enrolling in PMFBY crop insurance",
    "risk.improvement.formal_loan": "Consider replacing informal loans with bank loans at lower interest rates",

    # ===================================================================
    # Credit Guidance
    # ===================================================================
    "guidance.recommended_amount": "Based on your income and expenses, we recommend borrowing between ₹{min_amount:,.0f} and ₹{max_amount:,.0f}.",
    "guidance.timing_optimal": "The best time to take this loan is {start_month}/{start_year}.",
    "guidance.timing_reason": "This timing is {suitability} because {reason}.",
    "guidance.emi_info": "Your monthly EMI would be ₹{emi:,.0f} for {months} months.",
    "guidance.total_repayment": "Total repayment amount: ₹{total:,.0f} (principal + interest).",
    "guidance.capacity_warning": "Your current repayment capacity is limited. Consider a smaller loan amount.",
    "guidance.surplus_info": "After all expenses and existing EMIs, your average monthly surplus is ₹{surplus:,.0f}.",
    "guidance.alternative.shg": "Consider borrowing through your Self-Help Group at lower interest rates.",
    "guidance.alternative.kcc": "You may be eligible for a Kisan Credit Card (KCC) with subsidized rates.",
    "guidance.alternative.pmfby": "Enrolling in PMFBY crop insurance can reduce your financial risk.",
    "guidance.alternative.restructure": "Consolidating your existing loans may reduce your monthly burden.",
    "guidance.explanation.summary": "We analyzed your income, expenses, existing loans, and risk profile to generate this recommendation.",
    "guidance.confidence.high": "We have high confidence in this recommendation.",
    "guidance.confidence.medium": "This recommendation has moderate confidence. Actual conditions may vary.",
    "guidance.confidence.low": "This is a preliminary recommendation. We need more data for better accuracy.",

    # ===================================================================
    # Early Warning & Alerts
    # ===================================================================
    "alert.severity.info": "Information",
    "alert.severity.warning": "Warning",
    "alert.severity.critical": "Critical Alert",
    "alert.type.income_deviation": "Your income is lower than expected",
    "alert.type.repayment_stress": "You may face difficulty making loan repayments",
    "alert.type.over_indebtedness": "Your total debt is becoming too high",
    "alert.type.weather_risk": "Weather conditions may affect your income",
    "alert.type.market_risk": "Market price changes may affect your income",
    "alert.recommendation.reduce_spending": "Try to reduce non-essential expenses temporarily",
    "alert.recommendation.contact_bank": "Contact your bank to discuss repayment options",
    "alert.recommendation.seek_help": "Contact your nearest agricultural extension officer for assistance",
    "alert.recommendation.emergency_fund": "If possible, set aside a small amount each month for emergencies",

    # ===================================================================
    # Consent & Privacy
    # ===================================================================
    "consent.purpose.credit_assessment": "Credit Assessment",
    "consent.purpose.risk_scoring": "Risk Scoring",
    "consent.purpose.data_sharing_lender": "Sharing data with your lender",
    "consent.purpose.data_sharing_credit_bureau": "Sharing data with credit bureau",
    "consent.purpose.marketing": "Marketing communications",
    "consent.purpose.research_anonymized": "Anonymized research",
    "consent.purpose.government_scheme_matching": "Government scheme eligibility matching",
    "consent.purpose.early_warning_alerts": "Early warning alerts",
    "consent.grant_explanation": "By giving consent, you allow us to use your data for: {purpose}. You can revoke this consent at any time.",
    "consent.revoke_explanation": "Your consent for '{purpose}' has been revoked. We will stop using your data for this purpose.",
    "consent.data_usage_intro": "Here is how your data is being used:",
    "consent.data_retention": "Your {category} data will be kept for {days} days, after which it will be {action}.",
    "consent.your_rights": "You have the right to: view your data, download your data, revoke consent, and request deletion.",

    # ===================================================================
    # Loan Tracking
    # ===================================================================
    "loan.status.active": "Active",
    "loan.status.closed": "Closed",
    "loan.status.defaulted": "Defaulted",
    "loan.status.restructured": "Restructured",
    "loan.emi_due": "Your next EMI of ₹{amount:,.0f} is due on {date}.",
    "loan.payment_received": "We received your payment of ₹{amount:,.0f}. Thank you!",
    "loan.outstanding": "Your outstanding balance is ₹{balance:,.0f}.",
    "loan.source.formal": "Bank / NBFC Loan",
    "loan.source.semi_formal": "MFI / SHG Loan",
    "loan.source.informal": "Informal Loan",

    # ===================================================================
    # General UI
    # ===================================================================
    "general.welcome": "Welcome to Rural Credit Advisor",
    "general.loading": "Please wait...",
    "general.error": "Something went wrong. Please try again.",
    "general.success": "Done successfully!",
    "general.currency": "₹",
    "general.months": "months",
    "general.years": "years",
    "general.per_month": "per month",
    "general.per_year": "per year",

    # ===================================================================
    # Culturally Appropriate Examples (Req 10.3)
    # ===================================================================
    "cultural.income_example": "For example, if you earn ₹{amount:,.0f} from selling {crop} this season...",
    "cultural.emi_comparison": "This EMI is about the same as the cost of {bags} bags of fertilizer per month.",
    "cultural.savings_tip": "Setting aside even ₹500 per week — like the price of a bag of seeds — can build an emergency fund.",
    "cultural.seasons.kharif": "Kharif season (Jun-Oct, monsoon crops like rice, cotton, soybean)",
    "cultural.seasons.rabi": "Rabi season (Nov-Mar, winter crops like wheat, mustard, gram)",
    "cultural.seasons.zaid": "Zaid season (Mar-Jun, summer crops like watermelon, cucumber)",
    "cultural.loan_timing": "Taking a loan before {season} season lets you buy seeds and fertilizer at the right time.",
    "cultural.repayment_timing": "Repaying after harvest when you have more money helps avoid financial stress.",
    "cultural.shg_benefit": "Your Self-Help Group can help you access loans at 12-15% interest, much less than moneylenders.",
    "cultural.kcc_benefit": "A Kisan Credit Card gives you flexible credit up to ₹3 lakh at just 4% interest (with govt. subsidy).",
}

register_catalog(SupportedLanguage.ENGLISH, CATALOG)
