"""Kannada (ಕನ್ನಡ) message catalog for the Rural Credit Advisory System."""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # Risk Assessment
    "risk.category.low": "ಕಡಿಮೆ ಅಪಾಯ",
    "risk.category.medium": "ಮಧ್ಯಮ ಅಪಾಯ",
    "risk.category.high": "ಹೆಚ್ಚಿನ ಅಪಾಯ",
    "risk.category.very_high": "ಅತಿ ಹೆಚ್ಚಿನ ಅಪಾಯ",
    "risk.score_explanation": "ನಿಮ್ಮ ಅಪಾಯ ಅಂಕ 1000 ರಲ್ಲಿ {score}. ಕಡಿಮೆ ಅಂಕ ಎಂದರೆ ಕಡಿಮೆ ಅಪಾಯ.",
    "risk.factor.high_dti": "ನಿಮ್ಮ ಸಾಲ ಮರುಪಾವತಿಗಳು ನಿಮ್ಮ ಆದಾಯದ ದೊಡ್ಡ ಭಾಗವನ್ನು ತೆಗೆದುಕೊಳ್ಳುತ್ತವೆ",
    "risk.factor.seasonal_income": "ನಿಮ್ಮ ಆದಾಯ ಋತುಗಳ ನಡುವೆ ಗಮನಾರ್ಹವಾಗಿ ಬದಲಾಗುತ್ತದೆ",
    "risk.improvement.diversify": "ಆದಾಯ ಮೂಲಗಳನ್ನು ವೈವಿಧ್ಯಗೊಳಿಸುವುದನ್ನು ಪರಿಗಣಿಸಿ",
    "risk.improvement.insurance": "PMFBY ಬೆಳೆ ವಿಮೆಗೆ ನೋಂದಾಯಿಸಿಕೊಳ್ಳುವುದನ್ನು ಪರಿಗಣಿಸಿ",

    # Credit Guidance
    "guidance.recommended_amount": "ನಿಮ್ಮ ಆದಾಯ ಮತ್ತು ವೆಚ್ಚಗಳ ಆಧಾರದ ಮೇಲೆ, ₹{min_amount:,.0f} ರಿಂದ ₹{max_amount:,.0f} ನಡುವೆ ಸಾಲ ಪಡೆಯಲು ಸಲಹೆ ನೀಡುತ್ತೇವೆ.",
    "guidance.emi_info": "ನಿಮ್ಮ ಮಾಸಿಕ EMI ₹{emi:,.0f}, {months} ತಿಂಗಳುಗಳಿಗೆ.",
    "guidance.alternative.shg": "ಕಡಿಮೆ ಬಡ್ಡಿ ದರದಲ್ಲಿ ನಿಮ್ಮ ಸ್ವ-ಸಹಾಯ ಗುಂಪಿನ ಮೂಲಕ ಸಾಲ ಪಡೆಯಿರಿ.",
    "guidance.alternative.kcc": "ರಿಯಾಯಿತಿ ದರದಲ್ಲಿ ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್ (KCC) ಗೆ ನೀವು ಅರ್ಹರಾಗಿರಬಹುದು.",
    "guidance.explanation.summary": "ಈ ಶಿಫಾರಸಿಗಾಗಿ ನಿಮ್ಮ ಆದಾಯ, ವೆಚ್ಚಗಳು, ಸಾಲಗಳು ಮತ್ತು ಅಪಾಯ ಪ್ರೊಫೈಲ್ ವಿಶ್ಲೇಷಿಸಿದ್ದೇವೆ.",

    # Alerts
    "alert.severity.info": "ಮಾಹಿತಿ",
    "alert.severity.warning": "ಎಚ್ಚರಿಕೆ",
    "alert.severity.critical": "ತೀವ್ರ ಎಚ್ಚರಿಕೆ",
    "alert.type.income_deviation": "ನಿಮ್ಮ ಆದಾಯ ನಿರೀಕ್ಷಿತ ಮಟ್ಟಕ್ಕಿಂತ ಕಡಿಮೆ",
    "alert.type.repayment_stress": "ಸಾಲ ಮರುಪಾವತಿಯಲ್ಲಿ ತೊಂದರೆ ಇರಬಹುದು",
    "alert.recommendation.contact_bank": "ಮರುಪಾವತಿ ಆಯ್ಕೆಗಳನ್ನು ಚರ್ಚಿಸಲು ನಿಮ್ಮ ಬ್ಯಾಂಕನ್ನು ಸಂಪರ್ಕಿಸಿ",

    # Consent
    "consent.purpose.credit_assessment": "ಕ್ರೆಡಿಟ್ ಮೌಲ್ಯಮಾಪನ",
    "consent.purpose.risk_scoring": "ಅಪಾಯ ಮೌಲ್ಯಮಾಪನ",
    "consent.grant_explanation": "ಒಪ್ಪಿಗೆ ನೀಡುವ ಮೂಲಕ, ನಿಮ್ಮ ಡೇಟಾವನ್ನು ಬಳಸಲು ಅನುಮತಿಸುತ್ತೀರಿ: {purpose}. ಯಾವಾಗ ಬೇಕಾದರೂ ಹಿಂತೆಗೆದುಕೊಳ್ಳಬಹುದು.",
    "consent.your_rights": "ನಿಮ್ಮ ಹಕ್ಕುಗಳು: ಡೇಟಾ ವೀಕ್ಷಣೆ, ಡೌನ್\u200cಲೋಡ್, ಒಪ್ಪಿಗೆ ಹಿಂತೆಗೆತ, ಅಳಿಸುವಿಕೆ ವಿನಂತಿ.",

    # Loan
    "loan.status.active": "ಸಕ್ರಿಯ",
    "loan.status.closed": "ಮುಚ್ಚಲಾಗಿದೆ",
    "loan.emi_due": "ನಿಮ್ಮ ಮುಂದಿನ EMI ₹{amount:,.0f} {date} ರಂದು ಬರಬೇಕಾಗಿದೆ.",
    "loan.payment_received": "ನಿಮ್ಮ ₹{amount:,.0f} ಪಾವತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ಧನ್ಯವಾದಗಳು!",

    # General
    "general.welcome": "ಗ್ರಾಮೀಣ ಕ್ರೆಡಿಟ್ ಸಲಹೆಗಾರರಿಗೆ ಸ್ವಾಗತ",
    "general.loading": "ದಯವಿಟ್ಟು ನಿರೀಕ್ಷಿಸಿ...",
    "general.error": "ಏನೋ ತಪ್ಪಾಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    "general.success": "ಯಶಸ್ವಿಯಾಗಿ ಪೂರ್ಣಗೊಂಡಿತು!",

    # Cultural
    "cultural.seasons.kharif": "ಖಾರಿಫ್ ಋತು (ಜೂನ್-ಅಕ್ಟೋಬರ್, ಮಳೆಗಾಲದ ಬೆಳೆಗಳು: ಭತ್ತ, ಹತ್ತಿ)",
    "cultural.seasons.rabi": "ರಬಿ ಋತು (ನವೆಂಬರ್-ಮಾರ್ಚ್, ಚಳಿಗಾಲದ ಬೆಳೆಗಳು: ಗೋಧಿ, ಸಾಸಿವೆ)",
    "cultural.shg_benefit": "ನಿಮ್ಮ ಸ್ವ-ಸಹಾಯ ಗುಂಪು 12-15% ಬಡ್ಡಿಗೆ ಸಾಲ ನೀಡುತ್ತದೆ, ಇದು ಬಡ್ಡಿ ವ್ಯಾಪಾರಿಗಿಂತ ಕಡಿಮೆ.",
    "cultural.kcc_benefit": "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್ ₹3 ಲಕ್ಷದವರೆಗೆ 4% ಬಡ್ಡಿಗೆ (ಸರ್ಕಾರಿ ಸಹಾಯಧನ) ಸಾಲ ನೀಡುತ್ತದೆ.",
}

register_catalog(SupportedLanguage.KANNADA, CATALOG)
