"""Marathi (मराठी) message catalog for the Rural Credit Advisory System."""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # Risk Assessment
    "risk.category.low": "कमी जोखीम",
    "risk.category.medium": "मध्यम जोखीम",
    "risk.category.high": "उच्च जोखीम",
    "risk.category.very_high": "अत्यंत उच्च जोखीम",
    "risk.score_explanation": "तुमचा जोखीम गुण 1000 पैकी {score} आहे. कमी गुण म्हणजे कमी जोखीम.",
    "risk.factor.high_dti": "तुमच्या कर्ज परतफेडीसाठी तुमच्या उत्पन्नाचा मोठा भाग जातो",
    "risk.factor.seasonal_income": "तुमचे उत्पन्न हंगामानुसार लक्षणीयरित्या बदलते",
    "risk.improvement.diversify": "उत्पन्नाचे स्रोत विविधरित्या वाढवण्याचा विचार करा",
    "risk.improvement.insurance": "PMFBY पीक विमा योजनेत सहभागी होण्याचा विचार करा",

    # Credit Guidance
    "guidance.recommended_amount": "तुमच्या उत्पन्न आणि खर्चाच्या आधारावर, ₹{min_amount:,.0f} ते ₹{max_amount:,.0f} दरम्यान कर्ज घेण्याची शिफारस करतो.",
    "guidance.emi_info": "तुमची मासिक EMI ₹{emi:,.0f}, {months} महिन्यांसाठी.",
    "guidance.alternative.shg": "कमी व्याजदरात तुमच्या बचत गटामार्फत कर्ज घ्या.",
    "guidance.alternative.kcc": "सवलतीच्या दरात किसान क्रेडिट कार्ड (KCC) साठी तुम्ही पात्र असू शकता.",
    "guidance.explanation.summary": "या शिफारसीसाठी तुमचे उत्पन्न, खर्च, कर्जे आणि जोखीम प्रोफाइलचे विश्लेषण केले.",

    # Alerts
    "alert.severity.info": "माहिती",
    "alert.severity.warning": "सावधान",
    "alert.severity.critical": "गंभीर इशारा",
    "alert.type.income_deviation": "तुमचे उत्पन्न अपेक्षेपेक्षा कमी आहे",
    "alert.type.repayment_stress": "कर्ज परतफेडीत अडचण असू शकते",
    "alert.recommendation.contact_bank": "परतफेडीच्या पर्यायांबद्दल बँकेशी संपर्क साधा",

    # Consent
    "consent.purpose.credit_assessment": "पतमूल्यांकन",
    "consent.purpose.risk_scoring": "जोखीम मूल्यांकन",
    "consent.grant_explanation": "संमती देऊन, तुम्ही तुमचा डेटा वापरण्यास परवानगी देता: {purpose}. कधीही मागे घेता येते.",
    "consent.your_rights": "तुमचे हक्क: डेटा पाहणे, डाउनलोड, संमती मागे घेणे, डेटा हटवणे.",

    # Loan
    "loan.status.active": "सक्रिय",
    "loan.status.closed": "बंद",
    "loan.emi_due": "तुमची पुढील EMI ₹{amount:,.0f} {date} रोजी देय आहे.",
    "loan.payment_received": "तुमची ₹{amount:,.0f} ची भरणा मिळाली. धन्यवाद!",

    # General
    "general.welcome": "ग्रामीण पत सल्लागाराकडे स्वागत",
    "general.loading": "कृपया प्रतीक्षा करा...",
    "general.error": "काहीतरी चूक झाली. कृपया पुन्हा प्रयत्न करा.",
    "general.success": "यशस्वीरित्या पूर्ण!",

    # Cultural
    "cultural.seasons.kharif": "खरीप हंगाम (जून-ऑक्टोबर, पावसाळी पिके: भात, कापूस)",
    "cultural.seasons.rabi": "रब्बी हंगाम (नोव्हेंबर-मार्च, हिवाळी पिके: गहू, मोहरी)",
    "cultural.shg_benefit": "तुमचा बचत गट 12-15% व्याजाने कर्ज देतो, जे सावकारापेक्षा खूप कमी आहे.",
    "cultural.kcc_benefit": "किसान क्रेडिट कार्ड ₹3 लाखांपर्यंत 4% व्याजाने (सरकारी अनुदान) कर्ज देते.",
}

register_catalog(SupportedLanguage.MARATHI, CATALOG)
