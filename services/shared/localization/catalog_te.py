"""Telugu (తెలుగు) message catalog for the Rural Credit Advisory System."""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # Risk Assessment
    "risk.category.low": "తక్కువ ప్రమాదం",
    "risk.category.medium": "మధ్యస్థ ప్రమాదం",
    "risk.category.high": "అధిక ప్రమాదం",
    "risk.category.very_high": "చాలా అధిక ప్రమాదం",
    "risk.score_explanation": "మీ ప్రమాద స్కోరు 1000 లో {score}. తక్కువ స్కోరు అంటే తక్కువ ప్రమాదం.",
    "risk.factor.high_dti": "మీ రుణ తిరిగి చెల్లింపులు మీ ఆదాయంలో పెద్ద భాగం",
    "risk.factor.seasonal_income": "మీ ఆదాయం సీజన్ల అంతటా గణనీయంగా మారుతుంది",
    "risk.improvement.diversify": "ఆదాయ వనరులను వైవిధ్యం చేయడం ఆలోచించండి",
    "risk.improvement.insurance": "PMFBY పంట బీమాలో చేరడం ఆలోచించండి",

    # Credit Guidance
    "guidance.recommended_amount": "మీ ఆదాయం మరియు ఖర్చుల ఆధారంగా, ₹{min_amount:,.0f} నుండి ₹{max_amount:,.0f} మధ్య అప్పు తీసుకోమని సిఫార్సు చేస్తున్నాము.",
    "guidance.emi_info": "మీ నెలవారీ EMI ₹{emi:,.0f}, {months} నెలలకు.",
    "guidance.alternative.shg": "తక్కువ వడ్డీ రేట్లలో మీ స్వయం సహాయక సంఘం ద్వారా అప్పు తీసుకోండి.",
    "guidance.alternative.kcc": "రాయితీ రేట్లలో కిసాన్ క్రెడిట్ కార్డ్ (KCC) కు మీరు అర్హులు కావచ్చు.",
    "guidance.explanation.summary": "ఈ సిఫార్సు కోసం మీ ఆదాయం, ఖర్చులు, రుణాలు మరియు ప్రమాద ప్రొఫైల్ విశ్లేషించాము.",

    # Alerts
    "alert.severity.info": "సమాచారం",
    "alert.severity.warning": "హెచ్చరిక",
    "alert.severity.critical": "తీవ్ర హెచ్చరిక",
    "alert.type.income_deviation": "మీ ఆదాయం ఊహించిన దాని కంటే తక్కువ",
    "alert.type.repayment_stress": "రుణ తిరిగి చెల్లింపులో ఇబ్బంది ఉండవచ్చు",
    "alert.recommendation.contact_bank": "తిరిగి చెల్లింపు ఎంపికల గురించి మీ బ్యాంకును సంప్రదించండి",

    # Consent
    "consent.purpose.credit_assessment": "రుణ మూల్యాంకనం",
    "consent.purpose.risk_scoring": "ప్రమాద మూల్యాంకనం",
    "consent.grant_explanation": "సమ్మతి ఇవ్వడం ద్వారా, మీ డేటాను ఉపయోగించడానికి అనుమతిస్తారు: {purpose}. ఎప్పుడైనా రద్దు చేయవచ్చు.",
    "consent.your_rights": "మీ హక్కులు: డేటా చూడడం, డౌన్లోడ్, సమ్మతి రద్దు, తొలగింపు అభ్యర్థన.",

    # Loan
    "loan.status.active": "సక్రియం",
    "loan.status.closed": "మూసివేయబడింది",
    "loan.emi_due": "మీ తదుపరి EMI ₹{amount:,.0f} {date} న చెల్లించాలి.",
    "loan.payment_received": "మీ ₹{amount:,.0f} చెల్లింపు అందింది. ధన్యవాదాలు!",

    # General
    "general.welcome": "గ్రామీణ రుణ సలహాదారుకు స్వాగతం",
    "general.loading": "దయచేసి వేచి ఉండండి...",
    "general.error": "ఏదో తప్పు జరిగింది. దయచేసి మళ్ళీ ప్రయత్నించండి.",
    "general.success": "విజయవంతంగా పూర్తయింది!",

    # Cultural
    "cultural.seasons.kharif": "ఖరీఫ్ సీజన్ (జూన్-అక్టోబర్, వర్షాకాల పంటలు: వరి, పత్తి)",
    "cultural.seasons.rabi": "రబీ సీజన్ (నవంబర్-మార్చ్, శీతాకాల పంటలు: గోధుమ, ఆవాలు)",
    "cultural.shg_benefit": "మీ స్వయం సహాయక సంఘం 12-15% వడ్డీకి రుణాలు అందిస్తుంది, ఇది వడ్డీ వ్యాపారి కంటే చాలా తక్కువ.",
    "cultural.kcc_benefit": "కిసాన్ క్రెడిట్ కార్డ్ ₹3 లక్షల వరకు 4% వడ్డీకి (ప్రభుత్వ సబ్సిడీ) రుణం అందిస్తుంది.",
}

register_catalog(SupportedLanguage.TELUGU, CATALOG)
