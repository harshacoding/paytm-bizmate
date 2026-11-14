import type { Intent } from './demo';

export function followup(intent: Intent) {
  if (intent === 'payment')
    return {
      question: 'What would you like help understanding?',
      options: [
        'Explain the deductions',
        'What happens after I ask support?',
        'When can I check the missing credit?',
      ],
    };
  if (intent === 'campaign')
    return {
      question: 'What kind of offer would suit your customers?',
      options: ['A percentage discount', 'A free item with purchase', 'Help me choose an offer'],
    };
  if (intent === 'bank')
    return {
      question: 'What would you like to know before contacting support?',
      options: ['What information should I have ready?', 'How can I track my request?'],
    };
  return {
    question: 'What do you need help with today?',
    options: [
      'Why is my payment short?',
      'Help me bring customers back.',
      'How do I change my bank account?',
    ],
  };
}

export function answerFollowup(intent: Intent, answer: string): string {
  if (intent === 'payment') {
    if (/deduct|commission|gst|refund|chargeback|कटौती|कटौत|कमीशन|తగ్గింప|కమీషన్/i.test(answer))
      return 'In this sample, sales of ₹20,000 have ₹240 commission, ₹43.20 GST, ₹800 refunds and ₹350 for a disputed payment deducted. That leaves an expected ₹18,566.80. Open View details on the payment result to see each record.';
    if (/when|credit|check|tomorrow|today|yesterday|कब|कल|जाँच|ఎప్పుడు|రేపు|తనిఖీ/i.test(answer))
      return 'The demo uses one sample payment period. After confirming the support request above, choose Run simulated follow-up to check a fresh sample bank record for the ₹166.80 credit. The issue stays open until that credit is verified.';
    if (/support|request|ticket|सहायता|टिकट|అభ్యర్థన|సహాయం|టికెట్/i.test(answer))
      return 'Choose Ask support on the payment result, review the summary, then confirm the request. Your simulated ticket and follow-up control will appear in the same conversation.';
    return 'For this payment, I can explain the deductions, the support process, or the follow-up check. You can describe which part you need help with. The figures above come from the sample payment records.';
  }
  if (intent === 'campaign') {
    if (/percent|discount|10%|प्रतिशत|छूट|తగ్గింపు|శాతం/i.test(answer))
      return 'You could offer 10% off the next purchase this week. Edit the offer message above to set the discount and validity, then review the simulated send before confirming.';
    if (/free|item|purchase|मुफ्त|खरीद|ఉచిత|వస్తువు/i.test(answer))
      return 'You could offer a free item with the next purchase this week. Edit the offer above to name the item and any minimum purchase, then review the simulated send before confirming.';
    return 'Which product would you like to promote, and what discount or gift can your shop afford? Type your idea here, or edit the offer message above. The sample audience has 120 consenting customers and an estimated messaging cost of ₹240.';
  }
  if (intent === 'bank') {
    if (/track|status|request|स्थिति|अनुरोध|స్థితి|అభ్యర్థన/i.test(answer))
      return 'After you confirm the support request above, its ticket reference appears under View details. The bank account change remains pending with merchant support in this demo.';
    return 'Have your merchant reference and the new account holder name, account number and IFSC ready for merchant support through its secure process. You can create the simulated handoff using Ask support above.';
  }
  return 'Would you like to check a payment, prepare a customer offer, or ask support about a bank account change? Choose a suggestion or tell me in your own words.';
}
