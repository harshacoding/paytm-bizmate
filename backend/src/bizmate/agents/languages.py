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
    "payment_lookup_unavailable": (
        "I can't verify individual customer payments with the services connected here. "
        "Please use the transaction reference and approximate payment time when "
        "contacting payment support.",
        "ఇక్కడ అనుసంధానించిన సేవలతో వ్యక్తిగత కస్టమర్ చెల్లింపులను తనిఖీ చేయలేను. "
        "చెల్లింపు సహాయ బృందాన్ని సంప్రదించేటప్పుడు లావాదేవీ రిఫరెన్స్, "
        "సుమారు చెల్లింపు సమయం తెలియజేయండి.",
        "यहाँ जुड़ी सेवाओं से किसी ग्राहक के अलग भुगतान की स्थिति जाँच नहीं सकता। "
        "भुगतान सहायता से संपर्क करते समय लेनदेन संदर्भ और लगभग भुगतान समय बताएँ।",
    ),
    "chat_help": (
        "Hi! I can investigate settlement differences, prepare customer offers, or help "
        "you contact support. What would you like help with?",
        "నమస్తే! సెటిల్\u200cమెంట్ తేడాలను పరిశీలించగలను, కస్టమర్ ఆఫర్లను సిద్ధం చేయగలను "
        "లేదా సహాయ బృందాన్ని సంప్రదించడంలో సహాయపడగలను. మీకు ఏ సహాయం కావాలి?",
        "नमस्ते! मैं सेटलमेंट के अंतर की जाँच, ग्राहकों के लिए ऑफर तैयार करने या सहायता "
        "टीम से संपर्क करने में मदद कर सकता हूँ। आपको किस काम में मदद चाहिए?",
    ),
    "chat_thanks": (
        "You're welcome. What else can I help you with?",
        "మరే విషయంలోనైనా సహాయం కావాలా?",
        "और किस काम में मदद कर सकता हूँ?",
    ),
    "settlement_definition": (
        "A settlement is the transfer of your collected payments to your bank account "
        "after applicable deductions. I can investigate your settlement if you want to "
        "check a difference.",
        "సెటిల్\u200cమెంట్ అంటే వర్తించే తగ్గింపుల తర్వాత మీరు వసూలు చేసిన చెల్లింపులను మీ "
        "బ్యాంక్ ఖాతాకు బదిలీ చేయడం. తేడా ఉంటే పరిశీలించగలను.",
        "सेटलमेंट में लागू कटौतियों के बाद आपके एकत्रित भुगतान बैंक खाते में भेजे जाते "
        "हैं। राशि में अंतर हो तो मैं जाँच कर सकता हूँ।",
    ),
    "planner_unavailable": (
        "I couldn't process your request because the language service is unavailable. "
        "Please try again shortly. No action was taken.",
        "భాషా సేవ అందుబాటులో లేక మీ అభ్యర్థనను ప్రాసెస్ చేయలేకపోయాను. దయచేసి "
        "కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి. ఏ చర్యా తీసుకోలేదు.",
        "भाषा सेवा उपलब्ध नहीं होने के कारण आपका अनुरोध समझ नहीं सका। थोड़ी देर बाद फिर "
        "कोशिश करें। कोई कार्रवाई नहीं की गई।",
    ),
    "handoff_generic": (
        "The support reference was independently verified. The requested action remains "
        "pending with human support.",
        "సహాయ అభ్యర్థన విడిగా నిర్ధారించబడింది. కోరిన పని ప్రతినిధి వద్ద ఇంకా పెండింగ్‌లో ఉంది.",
        "सहायता संदर्भ अलग से सत्यापित हुआ। माँगा गया काम प्रतिनिधि के पास अभी लंबित है।",
    ),
    "handoff_limit": (
        "This request needs human support because the capability or permission is unavailable. "
        "Review the minimal support draft before approving. The requested change remains pending.",
        "ఈ పని చేయడానికి సౌకర్యం లేదా అనుమతి లేదు. ప్రతినిధి సహాయం అవసరం. "
        "ఆమోదించే ముందు సహాయ అభ్యర్థన పరిశీలించండి. కోరిన మార్పు ఇంకా పెండింగ్‌లో ఉంది.",
        "यह सुविधा या अनुमति उपलब्ध नहीं है। प्रतिनिधि की सहायता चाहिए। "
        "मंजूरी से पहले सहायता अनुरोध की समीक्षा करें। माँगा गया बदलाव अभी लंबित है।",
    ),
    "campaign_changed": (
        "The audience or offer changed. Review the updated recipients, message and cost "
        "and approve the new snapshot before sending.",
        "కస్టమర్లు లేదా ఆఫర్ మారింది. కొత్త కస్టమర్లు, సందేశం, ఖర్చు పరిశీలించి మళ్లీ ఆమోదించండి.",
        "ग्राहक सूची या ऑफर बदल गया। नई सूची, संदेश और लागत देखकर फिर से मंजूरी दें।",
    ),
    "settlement_done": (
        "Fresh synthetic credit resolves the settlement gap. No further follow-up is scheduled.",
        "కొత్త నమూనా జమతో సెటిల్‌మెంట్ తేడా పరిష్కరించబడింది. తదుపరి తనిఖీ అవసరం లేదు.",
        "नए नकली क्रेडिट से सेटलमेंट का अंतर हल हो गया। अगली जाँच निर्धारित नहीं है।",
    ),
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
        "Review the proposed action, audience, cost and evidence below. "
        "Approve to allow it, cancel it, or decide later.",
        "కింద ప్రతిపాదించిన పని, కస్టమర్లు, ఖర్చు, ఆధారాలు పరిశీలించండి. "
        "అనుమతించడానికి ఆమోదించండి, రద్దు చేయండి లేదా తర్వాత నిర్ణయించండి.",
        "नीचे प्रस्तावित काम, ग्राहकों, लागत और सबूत की समीक्षा करें। "
        "अनुमति देने के लिए मंजूरी दें, रद्द करें या बाद में तय करें।",
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
        "matching credit evidence. The next check is scheduled in demo time.",
        "సహాయ టికెట్ విడిగా నిర్ధారించబడింది. సరిపోయే కొత్త జమ ఆధారం వచ్చే వరకు సెటిల్‌మెంట్ పని తెరిచి ఉంటుంది. "
        "నమూనా సమయం ప్రకారం తదుపరి తనిఖీ నిర్ణయించబడింది.",
        "सहायता टिकट की अलग से पुष्टि हुई। मिलान वाला नया क्रेडिट सबूत मिलने तक "
        "सेटलमेंट खुला रहेगा। अगली जाँच डेमो समय के अनुसार निर्धारित है।",
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
