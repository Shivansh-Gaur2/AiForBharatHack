"""Hindi (हिन्दी) message catalog for the Rural Credit Advisory System."""

from services.shared.localization import SupportedLanguage, register_catalog

CATALOG: dict[str, str] = {
    # Risk Assessment
    "risk.category.low": "कम जोखिम",
    "risk.category.medium": "मध्यम जोखिम",
    "risk.category.high": "उच्च जोखिम",
    "risk.category.very_high": "अत्यधिक जोखिम",
    "risk.score_explanation": "आपका जोखिम स्कोर 1000 में से {score} है। कम स्कोर का मतलब कम जोखिम है।",
    "risk.factor.high_dti": "आपके कर्ज भुगतान आपकी आय का बड़ा हिस्सा ले रहे हैं",
    "risk.factor.low_dti": "आपका कर्ज-से-आय अनुपात स्वस्थ सीमा में है",
    "risk.factor.seasonal_income": "आपकी आय मौसम के अनुसार काफी बदलती है",
    "risk.factor.stable_income": "आपकी आय साल भर स्थिर रहती है",
    "risk.factor.no_insurance": "पंट बीमा न होने से खराब मौसम में जोखिम बढ़ जाता है",
    "risk.factor.has_insurance": "आपका फसल बीमा प्राकृतिक आपदाओं से सुरक्षा देता है",
    "risk.improvement.diversify": "आय के स्रोतों को विविध बनाने पर विचार करें",
    "risk.improvement.insurance": "PMFBY फसल बीमा में नामांकन पर विचार करें",
    "risk.improvement.reduce_debt": "ऊंची ब्याज वाले कर्जों का पहले भुगतान करें",
    "risk.improvement.savings": "फसल कटाई के बाद बचत करना शुरू करें",
    "risk.summary": "जोखिम सारांश: {category} ({score}/1000)। {factor_count} कारक विश्लेषित।",
    "risk.not_assessed": "अभी तक जोखिम मूल्यांकन नहीं किया गया है",

    # Credit Guidance
    "guidance.recommended_amount": "आपकी आय और खर्चों के आधार पर, हम ₹{min_amount:,.0f} से ₹{max_amount:,.0f} के बीच कर्ज लेने की सलाह देते हैं।",
    "guidance.emi_info": "आपकी मासिक EMI ₹{emi:,.0f} होगी, {months} महीनों के लिए।",
    "guidance.too_high": "अनुरोधित राशि आपकी भुगतान क्षमता से अधिक है। कम राशि पर विचार करें।",
    "guidance.affordable": "यह कर्ज राशि आपकी भुगतान क्षमता के भीतर है।",
    "guidance.alternative.shg": "कम ब्याज दर पर अपने स्वयं सहायता समूह (SHG) से कर्ज लें।",
    "guidance.alternative.kcc": "किसान क्रेडिट कार्ड (KCC) के लिए आप रियायती दर पर पात्र हो सकते हैं।",
    "guidance.alternative.mfi": "माइक्रोफाइनेंस संस्थान (MFI) छोटे कर्ज जल्दी दे सकते हैं।",
    "guidance.alternative.govt": "सरकारी योजनाओं से सब्सिडी वाला कर्ज मिल सकता है।",
    "guidance.explanation.summary": "इस सिफारिश के लिए हमने आपकी आय, खर्च, मौजूदा कर्ज और जोखिम प्रोफाइल का विश्लेषण किया।",
    "guidance.explanation.income_based": "सिफारिश आपकी {months} महीनों की औसत मासिक आय ₹{avg_income:,.0f} पर आधारित है।",
    "guidance.explanation.capacity": "आपकी अनुमानित मासिक भुगतान क्षमता ₹{capacity:,.0f} है।",
    "guidance.timing.best": "कर्ज लेने का सबसे अच्छा समय: {timing}",
    "guidance.timing.avoid": "इस समय कर्ज लेने से बचें: {reason}",
    "guidance.status.active": "सक्रिय सिफारिश",
    "guidance.status.expired": "समय-सीमा समाप्त सिफारिश",

    # Alerts
    "alert.severity.info": "सूचना",
    "alert.severity.warning": "चेतावनी",
    "alert.severity.critical": "गंभीर चेतावनी",
    "alert.type.income_deviation": "आपकी आय अपेक्षा से कम है",
    "alert.type.expense_spike": "खर्चों में असामान्य वृद्धि",
    "alert.type.repayment_stress": "कर्ज भुगतान में तनाव हो सकता है",
    "alert.type.weather_risk": "मौसम जोखिम: {event}",
    "alert.type.market_change": "बाजार मूल्य में बदलाव: {commodity}",
    "alert.recommendation.contact_bank": "भुगतान विकल्पों पर बात करने के लिए बैंक से संपर्क करें",
    "alert.recommendation.reduce_spending": "जब तक आय न बढ़े, गैर-जरूरी खर्च कम करें",
    "alert.recommendation.seek_help": "अपने स्थानीय कृषि सलाहकार से सहायता लें",
    "alert.dismissed": "चेतावनी खारिज कर दी गई",
    "alert.active_count": "आपकी {count} सक्रिय चेतावनियां हैं",

    # Consent
    "consent.purpose.credit_assessment": "ऋण मूल्यांकन",
    "consent.purpose.risk_scoring": "जोखिम मूल्यांकन",
    "consent.purpose.data_sharing_lender": "ऋणदाता के साथ डेटा साझा करना",
    "consent.purpose.data_sharing_bureau": "क्रेडिट ब्यूरो के साथ डेटा साझा करना",
    "consent.purpose.marketing": "विपणन संचार",
    "consent.purpose.research": "अनुसंधान (गोपनीय)",
    "consent.purpose.govt_scheme": "सरकारी योजना मिलान",
    "consent.grant_explanation": "सहमति देकर, आप अपने डेटा को इसके लिए उपयोग करने की अनुमति देते हैं: {purpose}। आप कभी भी इसे वापस ले सकते हैं।",
    "consent.revoke_confirm": "क्या आप {purpose} के लिए अपनी सहमति वापस लेना चाहते हैं?",
    "consent.revoked_success": "सहमति सफलतापूर्वक वापस ली गई",
    "consent.your_rights": "आपके अधिकार: अपना डेटा देखें, डाउनलोड करें, सहमति वापस लें, डेटा हटाने का अनुरोध करें।",
    "consent.data_usage": "आपका डेटा {service_count} सेवाओं द्वारा उपयोग किया जा रहा है",
    "consent.active_count": "आपकी {count} सक्रिय सहमतियां हैं",

    # Loan Tracking
    "loan.status.active": "सक्रिय",
    "loan.status.closed": "बंद",
    "loan.status.overdue": "अतिदेय",
    "loan.emi_due": "आपकी अगली EMI ₹{amount:,.0f} {date} को देय है।",
    "loan.payment_received": "आपका ₹{amount:,.0f} का भुगतान प्राप्त हुआ। धन्यवाद!",
    "loan.remaining_balance": "शेष राशि: ₹{balance:,.0f}",
    "loan.completion_date": "अनुमानित पूर्णता: {date}",
    "loan.overdue_warning": "आपकी EMI {days} दिन अतिदेय है। कृपया जल्द से जल्द भुगतान करें।",
    "loan.prepayment_benefit": "₹{amount:,.0f} की अग्रिम भुगतान से आप ₹{savings:,.0f} ब्याज बचा सकते हैं।",

    # General
    "general.welcome": "ग्रामीण ऋण सलाहकार में आपका स्वागत है",
    "general.loading": "कृपया प्रतीक्षा करें...",
    "general.error": "कुछ गलत हो गया। कृपया फिर से प्रयास करें।",
    "general.success": "सफलतापूर्वक पूर्ण!",
    "general.no_data": "कोई डेटा उपलब्ध नहीं है",
    "general.confirm": "क्या आप पुष्टि करते हैं?",
    "general.cancel": "रद्द करें",
    "general.back": "वापस जाएं",
    "general.help": "सहायता",

    # Cultural Context
    "cultural.emi_comparison": "यह EMI प्रति माह {bags} बोरी खाद की कीमत के बराबर है।",
    "cultural.savings_tip": "हर हफ्ते ₹500 भी बचाना - बीज की एक बोरी की कीमत जितना - आपातकालीन निधि बना सकता है।",
    "cultural.seasons.kharif": "खरीफ मौसम (जून-अक्टूबर, बारिश की फसलें जैसे धान, कपास, सोयाबीन)",
    "cultural.seasons.rabi": "रबी मौसम (नवंबर-मार्च, सर्दी की फसलें जैसे गेहूं, सरसों, चना)",
    "cultural.seasons.zaid": "ज़ायद मौसम (मार्च-जून, गर्मी की फसलें जैसे तरबूज़, खीरा)",
    "cultural.loan_timing": "{season} मौसम से पहले ऋण लेने से आप सही समय पर बीज और खाद खरीद सकते हैं।",
    "cultural.repayment_timing": "फसल कटाई के बाद भुगतान करना जब आपके पास अधिक पैसा होता है, वित्तीय तनाव से बचने में मदद करता है।",
    "cultural.shg_benefit": "आपका स्वयं सहायता समूह 12-15% ब्याज पर ऋण दे सकता है, जो साहूकार से बहुत कम है।",
    "cultural.kcc_benefit": "किसान क्रेडिट कार्ड ₹3 लाख तक 4% ब्याज (सरकारी सब्सिडी) पर ऋण देता है।",
    "cultural.pmfby_benefit": "प्रधानमंत्री फसल बीमा योजना (PMFBY) न्यूनतम प्रीमियम पर फसल बीमा प्रदान करती है।",
}

register_catalog(SupportedLanguage.HINDI, CATALOG)
