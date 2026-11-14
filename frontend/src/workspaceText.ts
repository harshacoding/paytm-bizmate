import { translate } from './i18n';
import type { LanguageCode } from './api/types';

// Interface labels only. Original API messages, evidence and identifiers are never translated here.
const copy: Record<string, [string, string]> = {
  'Scheduled time (demo clock)': ['निर्धारित समय (डेमो घड़ी)', 'నిర్దేశిత సమయం (డెమో గడియారం)'],
  'Settlement follow-up': ['सेटलमेंट की अगली जाँच', 'సెటిల్‌మెంట్ తదుపరి తనిఖీ'],
  'The ticket is verified. The settlement stays open until a fresh matching credit is verified.': [
    'टिकट की पुष्टि हुई। नया मिलान वाला क्रेडिट सत्यापित होने तक सेटलमेंट खुला रहेगा।',
    'టికెట్ ధృవీకరించబడింది. సరిపోయే కొత్త జమ నిర్ధారణ వరకు సెటిల్‌మెంట్ తెరిచి ఉంటుంది.',
  ],
  'This schedule uses the controlled demo clock, not your device time.': [
    'यह समय नियंत्रित डेमो घड़ी के अनुसार है, आपके उपकरण की घड़ी के अनुसार नहीं।',
    'ఈ షెడ్యూల్ నియంత్రిత డెమో గడియారాన్ని వాడుతుంది, మీ పరికర సమయాన్ని కాదు.',
  ],
  'Check due follow-ups': ['समय पर अगली जाँच करें', 'సమయం వచ్చిన తనిఖీలు చేయండి'],
  'Due follow-ups checked. Review the saved status and evidence.': [
    'समय पर अगली जाँच हुई। सहेजी स्थिति और सबूत देखें।',
    'సమయం వచ్చిన తనిఖీలు పూర్తయ్యాయి. భద్రపరచిన స్థితి, ఆధారాలు చూడండి.',
  ],
  'Checks due settlement tasks in this workspace without advancing demo time.': [
    'डेमो समय बढ़ाए बिना इस कार्यक्षेत्र में समय पर सेटलमेंट जाँच करता है।',
    'డెమో సమయం మార్చకుండా ఈ వర్క్‌స్పేస్‌లో సమయం వచ్చిన సెటిల్‌మెంట్లను తనిఖీ చేస్తుంది.',
  ],
  'Task continued. Check the current status and verification.': [
    'काम आगे बढ़ाया गया। वर्तमान स्थिति और पुष्टि देखें।',
    'పని కొనసాగించబడింది. ప్రస్తుత స్థితి, ధృవీకరణ చూడండి.',
  ],
  'Your clarification continues the saved task. Check its next action.': [
    'आपकी जानकारी से सहेजा काम आगे बढ़ता है। अगला कदम देखें।',
    'మీ సమాచారం భద్రపరచిన పనిని కొనసాగిస్తుంది. తదుపరి చర్యను చూడండి.',
  ],
  'Continue saved task': ['सहेजा काम जारी रखें', 'భద్రపరచిన పనిని కొనసాగించండి'],
  'Inspect saved action': ['सहेजी कार्रवाई जाँचें', 'భద్రపరచిన చర్యను పరిశీలించండి'],
  'Your permissions do not allow this action. Contact merchant support.': [
    'आपको इस कार्रवाई की अनुमति नहीं है। व्यापारी सहायता से संपर्क करें।',
    'ఈ చర్యకు మీకు అనుమతి లేదు. వ్యాపారి సహాయ బృందాన్ని సంప్రదించండి.',
  ],
  'Settlement source check': ['सेटलमेंट के स्रोत जाँचें', 'సెటిల్‌మెంట్ మూలాలను పరిశీలించండి'],
  'Check source records': ['स्रोत रिकॉर्ड जाँचें', 'మూల రికార్డులను పరిశీలించండి'],
  'This reads synthetic source records. It does not execute an action or complete the task.': [
    'यह नमूना स्रोत रिकॉर्ड पढ़ता है। इससे कार्रवाई या काम पूरा नहीं होता।',
    'ఇది నమూనా మూల రికార్డులను చదువుతుంది. ఇది చర్యను అమలు చేయదు లేదా పనిని పూర్తి చేయదు.',
  ],
  'Source comparison ready': ['स्रोतों की तुलना तैयार है', 'మూలాల పోలిక సిద్ధంగా ఉంది'],
  'Conflicting source records': ['स्रोत रिकॉर्ड में अंतर है', 'మూల రికార్డులు విరుద్ధంగా ఉన్నాయి'],
  'Some source records are missing': ['कुछ स्रोत रिकॉर्ड उपलब्ध नहीं हैं', 'కొన్ని మూల రికార్డులు లేవు'],
  'Still unexplained': ['अभी स्पष्ट नहीं', 'ఇంకా వివరణ లేదు'],
  Unknown: ['अज्ञात', 'తెలియదు'],
  Chargebacks: ['विवादित वापसी', 'వివాదాస్పద చెల్లింపుల వాపసు'],
  Sales: ['बिक्री', 'అమ్మకాలు'],
  Commission: ['कमीशन', 'కమీషన్'],
  'A source comparison is not proof that an unresolved credit has arrived.': [
    'स्रोतों की तुलना बकाया राशि आने का प्रमाण नहीं है।',
    'మూలాల పోలిక బకాయి మొత్తం జమైందని ఆధారం కాదు.',
  ],
  Saved: ['सहेजा गया', 'భద్రపరచబడింది'],
  Planning: ['योजना बन रही है', 'ప్రణాళిక సిద్ధమవుతోంది'],
  Ready: ['तैयार', 'సిద్ధంగా ఉంది'],
  Executing: ['कार्रवाई चल रही है', 'చర్య జరుగుతోంది'],
  'Needs your input': ['आपकी जानकारी चाहिए', 'మీ సమాచారం కావాలి'],
  'Needs approval': ['अनुमति चाहिए', 'ఆమోదం కావాలి'],
  'Pending externally': ['बाहरी सेवा के पास लंबित', 'బాహ్య సేవ వద్ద పెండింగ్'],
  Verifying: ['पुष्टि की जा रही है', 'ధృవీకరిస్తోంది'],
  'Goal completed': ['काम पूरा हुआ', 'పని పూర్తయింది'],
  'Escalated to support': ['सहायता टीम को सौंपा', 'సహాయ బృందానికి పంపబడింది'],
  Failed: ['असफल', 'విఫలమైంది'],
  'Task details': ['काम की जानकारी', 'పని వివరాలు'],
  'Back to chat': ['चैट पर लौटें', 'చాట్‌కు తిరిగి వెళ్ళండి'],
  'Loading task…': ['काम लोड हो रहा है…', 'పని లోడ్ అవుతోంది…'],
  Refresh: ['फिर से देखें', 'తాజాగా చూడండి'],
  'Synthetic data · Simulated actions': ['नमूना डेटा · डेमो कार्रवाइयाँ', 'నమూనా సమాచారం · డెమో చర్యలు'],
  'Next action': ['अगला कदम', 'తదుపరి చర్య'],
  'Scheduled time': ['निर्धारित समय', 'నిర్దేశిత సమయం'],
  'Execution is not guaranteed by this timestamp.': [
    'यह समय कार्रवाई होने की गारंटी नहीं है।',
    'ఈ సమయానికి చర్య జరుగుతుందని హామీ లేదు.',
  ],
  'Action needs attention': ['कार्रवाई पर ध्यान दें', 'చర్యను పరిశీలించండి'],
  'Refresh saved records before trying another action.': [
    'दूसरी कार्रवाई से पहले सहेजे गए रिकॉर्ड फिर देखें।',
    'మరో చర్యకు ముందు భద్రపరచిన రికార్డులను తాజాగా చూడండి.',
  ],
  'Outcome unresolved': ['नतीजे की पुष्टि बाकी है', 'ఫలితం ఇంకా నిర్ధారణ కాలేదు'],
  'Do not resend. A request may already have reached the provider. Refresh the task and inspect its receipt.':
    [
      'दोबारा न भेजें। अनुरोध सेवा तक पहुँच चुका हो सकता है। काम फिर देखें और रसीद जाँचें।',
      'మళ్ళీ పంపవద్దు. అభ్యర్థన ఇప్పటికే సేవకు చేరి ఉండవచ్చు. పనిని తాజాగా చూసి రసీదును పరిశీలించండి.',
    ],
  'Add clarification': ['और जानकारी दें', 'మరింత సమాచారం ఇవ్వండి'],
  'Save clarification': ['जानकारी सहेजें', 'సమాచారం భద్రపరచండి'],
  'Saving a clarification does not mean execution has resumed.': [
    'जानकारी सहेजने का मतलब कार्रवाई शुरू होना नहीं है।',
    'సమాచారం భద్రపరచడం అంటే చర్య తిరిగి మొదలైందని కాదు.',
  ],
  'Clarification saved. The backend will determine the next step.': [
    'जानकारी सहेजी गई। अगला कदम सेवा तय करेगी।',
    'సమాచారం భద్రపరచబడింది. తదుపరి చర్యను సేవ నిర్ణయిస్తుంది.',
  ],
  'Financial evidence': ['भुगतान के प्रमाण', 'చెల్లింపు ఆధారాలు'],
  Captured: ['रिकॉर्ड किया गया', 'నమోదైన సమయం'],
  'Review your offer': ['ऑफर की समीक्षा करें', 'మీ ఆఫర్‌ను సమీక్షించండి'],
  'Prepare support request': ['सहायता अनुरोध तैयार करें', 'సహాయ అభ్యర్థన సిద్ధం చేయండి'],
  'Days since last visit': ['पिछली खरीदारी से दिन', 'చివరి కొనుగోలు నుండి రోజులు'],
  'Find eligible customers': ['पात्र ग्राहक खोजें', 'అర్హత గల కస్టమర్లను కనుగొనండి'],
  'Eligible audience loaded': ['पात्र ग्राहक मिल गए', 'అర్హత గల కస్టమర్లు సిద్ధంగా ఉన్నారు'],
  'customers who agreed to receive offers': [
    'ग्राहकों ने ऑफर पाने की सहमति दी है',
    'కస్టమర్లు ఆఫర్లు పొందేందుకు అంగీకరించారు',
  ],
  'Estimated cost': ['अनुमानित लागत', 'అంచనా ఖర్చు'],
  Evaluated: ['जाँचा गया', 'పరిశీలించిన సమయం'],
  'Histories reviewed': ['ग्राहक रिकॉर्ड जाँचे', 'పరిశీలించిన కస్టమర్ రికార్డులు'],
  'Excluded without consent': ['सहमति न होने पर हटाए गए', 'అనుమతి లేక తొలగించినవి'],
  'Offer message': ['ऑफर संदेश', 'ఆఫర్ సందేశం'],
  'Support summary': ['सहायता अनुरोध का सार', 'సహాయ అభ్యర్థన సారాంశం'],
  'Review approval': ['अनुमति की समीक्षा करें', 'ఆమోదాన్ని సమీక్షించండి'],
  'No campaign is sent until you approve and execute the saved offer and cost.': [
    'सहेजे गए ऑफर और लागत को मंजूरी देकर कार्रवाई करने तक प्रचार नहीं भेजा जाएगा।',
    'భద్రపరచిన ఆఫర్, ఖర్చును ఆమోదించి అమలు చేసే వరకు ప్రచారం పంపబడదు.',
  ],
  'This will create a simulated support ticket. It will not prove a missing bank credit arrived.': [
    'इससे डेमो सहायता टिकट बनेगा। यह बैंक में बकाया राशि आने का प्रमाण नहीं है।',
    'ఇది డెమో సహాయ టికెట్‌ను సృష్టిస్తుంది. బ్యాంకులో బకాయి జమైందని ఇది నిర్ధారించదు.',
  ],
  'Approval snapshot saved. Review it before approving.': [
    'अनुमति का विवरण सहेजा गया। मंजूरी से पहले समीक्षा करें।',
    'ఆమోద వివరాలు భద్రపరచబడ్డాయి. ఆమోదించే ముందు సమీక్షించండి.',
  ],
  'Approval snapshot': ['अनुमति का निश्चित विवरण', 'ఆమోదానికి ఖచ్చితమైన వివరాలు'],
  'Pending approval': ['अनुमति बाकी है', 'ఆమోదం పెండింగ్‌లో ఉంది'],
  Approved: ['मंजूरी मिली', 'ఆమోదించబడింది'],
  Cancelled: ['रद्द हुआ', 'రద్దు చేయబడింది'],
  Recipients: ['प्राप्तकर्ता', 'గ్రహీతలు'],
  'Approval authorises this exact offer, audience and cost. Sending and verification are separate steps.':
    [
      'मंजूरी इसी ऑफर, ग्राहक सूची और लागत के लिए है। भेजना और पुष्टि अलग कदम हैं।',
      'ఈ ఆమోదం ఈ ఆఫర్, కస్టమర్లు, ఖర్చుకు మాత్రమే. పంపడం, ధృవీకరణ వేర్వేరు చర్యలు.',
    ],
  'Approval authorises this exact support summary. A ticket is not proof that the merchant issue is resolved.':
    [
      'मंजूरी इसी सहायता सार के लिए है। टिकट बनना समस्या हल होने का प्रमाण नहीं है।',
      'ఈ ఆమోదం ఈ సహాయ సారాంశానికి మాత్రమే. టికెట్ సమస్య పరిష్కారానికి ఆధారం కాదు.',
    ],
  'Decision recorded': ['निर्णय दर्ज किया गया', 'నిర్ణయం నమోదైంది'],
  'Exact input hash': ['निश्चित विवरण का हैश', 'ఖచ్చితమైన వివరాల హాష్'],
  Approve: ['मंजूरी दें', 'ఆమోదించండి'],
  'Decide later': ['बाद में तय करें', 'తరువాత నిర్ణయించండి'],
  'Approved. Execution has not started.': [
    'मंजूरी मिली। कार्रवाई शुरू नहीं हुई है।',
    'ఆమోదించబడింది. చర్య ఇంకా ప్రారంభం కాలేదు.',
  ],
  'Cancelled. Replanning must be handled by the backend.': [
    'रद्द हुआ। सेवा को दोबारा योजना बनानी होगी।',
    'రద్దు చేయబడింది. సేవ మళ్ళీ ప్రణాళిక చేయాలి.',
  ],
  'Execute approved action': ['मंजूर कार्रवाई करें', 'ఆమోదించిన చర్యను అమలు చేయండి'],
  'Action executed. Independent verification is still required.': [
    'कार्रवाई की गई। स्वतंत्र पुष्टि अभी बाकी है।',
    'చర్య అమలైంది. స్వతంత్ర ధృవీకరణ ఇంకా అవసరం.',
  ],
  'Execution receipts': ['कार्रवाई की रसीदें', 'చర్య రసీదులు'],
  Executed: ['कार्रवाई की गई', 'అమలు చేయబడింది'],
  'Not verified': ['पुष्टि नहीं हुई', 'ధృవీకరించబడలేదు'],
  'Action verified': ['कार्रवाई की पुष्टि हुई', 'చర్య ధృవీకరించబడింది'],
  'Verification failed': ['पुष्टि असफल रही', 'ధృవీకరణ విఫలమైంది'],
  'Ticket reference': ['टिकट संदर्भ', 'టికెట్ సూచన'],
  'Campaign reference': ['प्रचार संदर्भ', 'ప్రచార సూచన'],
  'Executed at': ['कार्रवाई का समय', 'అమలు చేసిన సమయం'],
  'Verified at': ['पुष्टि का समय', 'ధృవీకరించిన సమయం'],
  'A verified action does not mean the task goal is complete. Follow the backend task status and next action.':
    [
      'कार्रवाई की पुष्टि का मतलब काम पूरा होना नहीं है। सेवा की स्थिति और अगला कदम देखें।',
      'చర్య ధృవీకరణ అంటే పని పూర్తయిందని కాదు. సేవ చూపే పని స్థితి, తదుపరి చర్యను చూడండి.',
    ],
  'Verification did not confirm the action. The work remains unresolved.': [
    'पुष्टि में कार्रवाई प्रमाणित नहीं हुई। काम अभी अनसुलझा है।',
    'ధృవీకరణ చర్యను నిర్ధారించలేదు. పని ఇంకా పరిష్కారం కాలేదు.',
  ],
  'Verification attempt recorded': ['पुष्टि की कोशिश दर्ज हुई', 'ధృవీకరణ ప్రయత్నం నమోదైంది'],
  'Check verification again': ['फिर से पुष्टि जाँचें', 'మళ్ళీ ధృవీకరణ చూడండి'],
  'Verify action': ['कार्रवाई की पुष्टि करें', 'చర్యను ధృవీకరించండి'],
  'Support handoff': ['सहायता टीम को सौंपना', 'సహాయ బృందానికి అప్పగింత'],
  'Activity timeline': ['कार्रवाई का क्रम', 'చర్యల కాలక్రమం'],
  'No activity recorded yet.': ['अभी कोई कार्रवाई दर्ज नहीं है।', 'ఇంకా ఏ చర్య నమోదు కాలేదు.'],
  'Plan progress': ['योजना की प्रगति', 'ప్రణాళిక పురోగతి'],
  'Task reference': ['काम का संदर्भ', 'పని సూచన'],
  Revision: ['संस्करण', 'సవరణ'],
  Updated: ['अपडेट किया गया', 'నవీకరించబడింది'],
  'Your merchant permissions allow viewing only.': [
    'आपकी अनुमति केवल देखने के लिए है।',
    'మీ అనుమతులతో చూడటం మాత్రమే సాధ్యం.',
  ],
  'Connecting to your workspace…': ['आपके काम से जुड़ रहे हैं…', 'మీ పనుల విభాగానికి అనుసంధానిస్తోంది…'],
  'Workspace unavailable': ['काम का पृष्ठ उपलब्ध नहीं है', 'పనుల విభాగం అందుబాటులో లేదు'],
  'Retry connection': ['फिर से जुड़ें', 'మళ్ళీ అనుసంధానించండి'],
  'Saved on the server': ['सर्वर पर सहेजा गया', 'సర్వర్‌లో భద్రపరచబడింది'],
  'Your tasks': ['आपके काम', 'మీ పనులు'],
  'No tasks yet': ['अभी कोई काम नहीं है', 'ఇంకా పనులు లేవు'],
  Conversation: ['बातचीत', 'సంభాషణ'],
  'Task clarification': ['काम की जानकारी', 'పని స్పష్టీకరణ'],
  'Message not confirmed': ['संदेश की पुष्टि नहीं हुई', 'సందేశం నిర్ధారణ కాలేదు'],
  'Retry this exact message': ['यही संदेश फिर भेजें', 'ఇదే సందేశాన్ని మళ్ళీ పంపండి'],
  'Start a task from this question': ['इस सवाल से काम शुरू करें', 'ఈ ప్రశ్నతో పని ప్రారంభించండి'],
  'This creates a separate tracked task. Chat alone does not start execution.': [
    'यह अलग काम का रिकॉर्ड बनाएगा। केवल चैट से कार्रवाई शुरू नहीं होती।',
    'ఇది ప్రత్యేక పని రికార్డును సృష్టిస్తుంది. చాట్ మాత్రమే చర్యను ప్రారంభించదు.',
  ],
  'Sample walkthrough': ['नमूना डेमो', 'నమూనా డెమో'],
  'Loading conversation…': ['बातचीत लोड हो रही है…', 'సంభాషణ లోడ్ అవుతోంది…'],
  'Sending your message…': ['आपका संदेश भेज रहे हैं…', 'మీ సందేశాన్ని పంపుతోంది…'],
  'Chat uses saved server messages. Business execution starts only through a tracked task.': [
    'चैट में सर्वर के सहेजे संदेश हैं। कार्रवाई केवल दर्ज काम से शुरू होती है।',
    'చాట్‌లో సర్వర్‌లో భద్రపరచిన సందేశాలు ఉంటాయి. నమోదు చేసిన పని ద్వారా మాత్రమే చర్య ప్రారంభమవుతుంది.',
  ],
  'All tasks': ['सभी काम', 'అన్ని పనులు'],
  'Tasks in this chat': ['इस चैट के काम', 'ఈ చాట్‌లోని పనులు'],
};

export function workspaceText(text: string, language: LanguageCode) {
  return language === 'en'
    ? text
    : (copy[text]?.[language === 'hi' ? 0 : 1] ?? translate(text, language));
}
