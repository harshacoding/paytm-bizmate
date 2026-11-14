"""Presentation only. Language selection never supplies tool inputs or permissions."""

import re

from bizmate.domain.models import LanguageCode


def detect_language(text: str) -> LanguageCode | None:
    # Count words, not code points (Indic words contain combining characters).
    counts = {
        "te": len(re.findall(r"[\u0c00-\u0c7f]+", text)),
        "hi": len(re.findall(r"[\u0900-\u097f]+", text)),
        "en": len(re.findall(r"[A-Za-z]+", text)),
    }
    best = max(counts, key=counts.get)
    leaders = [key for key, value in counts.items() if value == counts[best]]
    return LanguageCode(best) if counts[best] and len(leaders) == 1 else None


MESSAGES = {
    "intake": (
        "Request understood. Start a task to prepare evidence and review any proposed action.",
        "అభ్యర్థన అర్థమైంది. ఆధారాలు సిద్ధం చేసి ప్రతిపాదించిన పనిని పరిశీలించడానికి పని ప్రారంభించండి.",
        "अनुरोध समझा गया। सबूत तैयार करने और प्रस्तावित काम की समीक्षा के लिए कार्य शुरू करें।",
    ),
    "settlement_summary": (
        "Expected ₹{expected}, credited ₹{credit}, unexplained gap ₹{gap}. "
        "Proposed action: create a support ticket using the attached sources.",
        "అంచనా ₹{expected}, జమ ₹{credit}, వివరించని తేడా ₹{gap}. "
        "ప్రతిపాదిత పని: జతచేసిన ఆధారాలతో సహాయ టికెట్ సృష్టించడం.",
        "अपेक्षित ₹{expected}, जमा ₹{credit}, अस्पष्ट अंतर ₹{gap}। "
        "प्रस्तावित काम: संलग्न स्रोतों के साथ सहायता टिकट बनाना।",
    ),
    "campaign_summary": (
        "Send this exact message to {count} consenting inactive customers for ₹{cost}: {message}",
        "సమ్మతి ఉన్న {count} మంది రాని కస్టమర్లకు ₹{cost} ఖర్చుతో ఈ సందేశం పంపండి: {message}",
        "सहमति वाले {count} निष्क्रिय ग्राहकों को ₹{cost} में यही संदेश भेजें: {message}",
    ),
    "clarify": (
        "Please choose one request: investigate a settlement, send an inactive-customer offer, "
        "or request a bank-account support handoff.",
        "దయచేసి ఒక పని ఎంచుకోండి: సెటిల్‌మెంట్ పరిశీలన, రాని కస్టమర్లకు ఆఫర్, లేదా బ్యాంక్ ఖాతా సహాయం.",
        "कृपया एक काम चुनें: सेटलमेंट की जाँच, निष्क्रिय ग्राहकों को ऑफर, या बैंक खाते के लिए सहायता।",
    ),
    "offer": (
        'What exact offer should be sent? Reply with message="your offer text".',
        'ఏ ఆఫర్ పంపాలి? message="మీ ఆఫర్ వాక్యం" అని సమాధానం ఇవ్వండి.',
        'कौन सा ऑफर भेजना है? message="आपका ऑफर" लिखकर उत्तर दें।',
    ),
    "approval": (
        "Review the exact saved action, audience, cost and evidence. Approve its input hash "
        "using the approval API, then resume the task.",
        "భద్రపరచిన పని, కస్టమర్లు, ఖర్చు, ఆధారాలు పరిశీలించండి. ఆమోద APIలో input hash ఆమోదించి పనిని కొనసాగించండి.",
        "सहेजे गए काम, ग्राहकों, लागत और सबूत की समीक्षा करें। "
        "अनुमोदन API में input hash मंजूर करें और काम फिर शुरू करें।",
    ),
    "running": (
        "Executing the validated plan.",
        "పరిశీలించిన ప్రణాళిక అమలవుతోంది.",
        "जाँची गई योजना पर काम हो रहा है।",
    ),
    "error": (
        "Recovery needs review. Evidence and errors are saved. No successful outcome is confirmed.",
        "పునరుద్ధరణకు సమీక్ష అవసరం. ఆధారాలు, లోపాలు భద్రపరచబడ్డాయి. ఫలితం నిర్ధారించలేదు.",
        "पुनर्प्राप्ति की समीक्षा चाहिए। सबूत और त्रुटियाँ सहेजी गई हैं। सफलता की पुष्टि नहीं हुई।",
    ),
    "read_error": (
        "A read failed. The bounded recovery attempt was saved.",
        "చదవడంలో లోపం. పరిమిత పునరుద్ధరణ ప్రయత్నం భద్రపరచబడింది.",
        "पढ़ने में त्रुटि हुई। सीमित पुनर्प्राप्ति प्रयास सहेजा गया।",
    ),
    "fallback": (
        "Report unavailable. Using independently sourced payment records.",
        "రిపోర్టు అందుబాటులో లేదు. విడిగా పొందిన చెల్లింపు ఆధారాలు వాడుతున్నాము.",
        "रिपोर्ट उपलब्ध नहीं है। अलग से प्राप्त भुगतान रिकॉर्ड इस्तेमाल हो रहे हैं।",
    ),
    "settlement_wait": (
        "The support ticket was independently verified. Settlement remains open pending fresh "
        "matching credit evidence. Follow-up scheduling is a separate workflow.",
        "సహాయ టికెట్ విడిగా నిర్ధారించబడింది. సరిపోయే కొత్త జమ ఆధారం వచ్చే వరకు సెటిల్‌మెంట్ పని తెరిచి ఉంటుంది. తదుపరి తనిఖీ వేరే పని.",
        "सहायता टिकट की अलग से पुष्टि हुई। मिलान वाला नया क्रेडिट सबूत मिलने तक "
        "सेटलमेंट खुला रहेगा। अगली जाँच अलग कार्य है।",
    ),
    "campaign_done": (
        "Campaign delivery was independently verified. Delivered {delivered}, failed {failed}. "
        "Delivery does not establish sales uplift.",
        "ప్రచార పంపిణీ విడిగా నిర్ధారించబడింది. చేరినవి {delivered}, విఫలమైనవి {failed}. దీనితో అమ్మకాల పెరుగుదల నిర్ధారణ కాదు.",
        "अभियान की डिलीवरी अलग से सत्यापित हुई। पहुँचे {delivered}, असफल {failed}। "
        "इससे बिक्री बढ़ने की पुष्टि नहीं होती।",
    ),
    "handoff": (
        "Support handoff verified. A human must complete the bank-account change.",
        "సహాయ అభ్యర్థన నిర్ధారించబడింది. బ్యాంక్ ఖాతా మార్పును ప్రతినిధి పూర్తి చేయాలి.",
        "सहायता अनुरोध सत्यापित हुआ। बैंक खाते का बदलाव प्रतिनिधि को पूरा करना होगा।",
    ),
    "cancelled": (
        "Action cancelled. Send a new request to review a new plan.",
        "పని రద్దయింది. కొత్త ప్రణాళిక కోసం కొత్త అభ్యర్థన పంపండి.",
        "कार्रवाई रद्द हुई। नई योजना के लिए नया अनुरोध भेजें।",
    ),
    "recovered": (
        "An uncertain write was found in provider records. Its receipt was recovered.",
        "నిర్ధారణ లేని పని ప్రొవైడర్ ఆధారాల్లో దొరికింది. రసీదు తిరిగి పొందబడింది.",
        "अनिश्चित कार्रवाई प्रदाता के रिकॉर्ड में मिली। रसीद पुनः प्राप्त हुई।",
    ),
}


def say(key: str, language: str, **values) -> str:
    return MESSAGES[key][{"en": 0, "te": 1, "hi": 2}[language]].format(**values)
