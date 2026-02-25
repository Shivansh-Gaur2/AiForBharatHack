"""Tamil (தமிழ்) message catalog for the Rural Credit Advisory System."""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # Risk Assessment
    "risk.category.low": "குறைந்த ஆபத்து",
    "risk.category.medium": "நடுத்தர ஆபத்து",
    "risk.category.high": "அதிக ஆபத்து",
    "risk.category.very_high": "மிக அதிக ஆபத்து",
    "risk.score_explanation": "உங்கள் ஆபத்து மதிப்பெண் 1000 இல் {score}. குறைவான மதிப்பெண் குறைவான ஆபத்தைக் குறிக்கிறது.",
    "risk.factor.high_dti": "உங்கள் கடன் திருப்பிச் செலுத்துதல் உங்கள் வருமானத்தின் பெரும்பகுதியை எடுக்கிறது",
    "risk.factor.seasonal_income": "உங்கள் வருமானம் பருவங்களுக்கு இடையில் கணிசமாக மாறுகிறது",
    "risk.improvement.diversify": "வருமான ஆதாரங்களை பன்முகப்படுத்துவதை கருத்தில் கொள்ளுங்கள்",
    "risk.improvement.insurance": "PMFBY பயிர் காப்பீட்டில் சேர்வதை கருத்தில் கொள்ளுங்கள்",

    # Credit Guidance
    "guidance.recommended_amount": "உங்கள் வருமானம் மற்றும் செலவுகளின் அடிப்படையில், ₹{min_amount:,.0f} முதல் ₹{max_amount:,.0f} வரை கடன் பெற பரிந்துரைக்கிறோம்.",
    "guidance.emi_info": "உங்கள் மாதாந்திர EMI ₹{emi:,.0f}, {months} மாதங்களுக்கு.",
    "guidance.alternative.shg": "குறைந்த வட்டி விகிதத்தில் உங்கள் சுய உதவிக் குழு மூலம் கடன் பெறுங்கள்.",
    "guidance.alternative.kcc": "சலுகை விகிதத்தில் கிசான் கிரெடிட் கார்டு (KCC) க்கு நீங்கள் தகுதி பெறலாம்.",
    "guidance.explanation.summary": "இந்த பரிந்துரைக்காக உங்கள் வருமானம், செலவுகள், கடன்கள் மற்றும் ஆபத்து விவரக்குறிப்பு ஆகியவற்றை ஆய்வு செய்தோம்.",

    # Alerts
    "alert.severity.info": "தகவல்",
    "alert.severity.warning": "எச்சரிக்கை",
    "alert.severity.critical": "அவசர எச்சரிக்கை",
    "alert.type.income_deviation": "உங்கள் வருமானம் எதிர்பார்த்ததை விட குறைவாக உள்ளது",
    "alert.type.repayment_stress": "கடன் திருப்பிச் செலுத்துவதில் சிரமம் இருக்கலாம்",
    "alert.recommendation.contact_bank": "திருப்பிச் செலுத்தும் விருப்பங்களை விவாதிக்க உங்கள் வங்கியை தொடர்பு கொள்ளுங்கள்",

    # Consent
    "consent.purpose.credit_assessment": "கடன் மதிப்பீடு",
    "consent.purpose.risk_scoring": "ஆபத்து மதிப்பீடு",
    "consent.grant_explanation": "ஒப்புதல் அளிப்பதன் மூலம், உங்கள் தரவை பயன்படுத்த அனுமதிக்கிறீர்கள்: {purpose}. எப்போது வேண்டுமானாலும் திரும்பப் பெறலாம்.",
    "consent.your_rights": "உங்கள் உரிமைகள்: தரவு பார்வை, பதிவிறக்கம், ஒப்புதல் திரும்பப் பெறல், நீக்கம் கோரிக்கை.",

    # Loan
    "loan.status.active": "செயலில்",
    "loan.status.closed": "மூடப்பட்டது",
    "loan.emi_due": "உங்கள் அடுத்த EMI ₹{amount:,.0f} {date} அன்று செலுத்த வேண்டும்.",
    "loan.payment_received": "உங்கள் ₹{amount:,.0f} பணம் பெறப்பட்டது. நன்றி!",

    # General
    "general.welcome": "கிராமப்புற கடன் ஆலோசகருக்கு வரவேற்கிறோம்",
    "general.loading": "தயவுசெய்து காத்திருங்கள்...",
    "general.error": "ஏதோ தவறு நடந்தது. தயவுசெய்து மீண்டும் முயற்சிக்கவும்.",
    "general.success": "வெற்றிகரமாக முடிந்தது!",

    # Cultural
    "cultural.seasons.kharif": "கரீப் பருவம் (ஜூன்-அக்டோபர், மழைக்கால பயிர்கள்: நெல், பருத்தி)",
    "cultural.seasons.rabi": "ரபி பருவம் (நவம்பர்-மார்ச், குளிர்கால பயிர்கள்: கோதுமை, கடுகு)",
    "cultural.shg_benefit": "உங்கள் சுய உதவிக் குழு 12-15% வட்டியில் கடன் தருகிறது, இது வட்டி வியாபாரியை விட மிகக் குறைவு.",
    "cultural.kcc_benefit": "கிசான் கிரெடிட் கார்டு ₹3 லட்சம் வரை 4% வட்டியில் (அரசு மானியம்) கடன் தருகிறது.",
}

register_catalog(SupportedLanguage.TAMIL, CATALOG)
