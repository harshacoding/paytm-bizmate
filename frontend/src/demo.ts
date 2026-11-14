export const questions = [
  'Why is my payment short?',
  'Help me bring customers back.',
  'How do I change my bank account?',
  'Review my sales report.',
];
export const stages = [
  { at: 0, progress: 20, label: 'Fetching your payment records' },
  { at: 1800, progress: 60, label: 'Analysing your transactions' },
  { at: 5000, progress: 90, label: 'Comparing sales with your bank payment' },
  { at: 6900, progress: 100, label: 'Payment check finished' },
];
export const breakdown = [
  { label: 'Sales', paise: 2000000, source: 'Sales report · SALES-2026-011' },
  { label: 'Commission', paise: -24000, source: 'Payment report · PAY-2026-011' },
  { label: 'GST on commission', paise: -4320, source: 'Payment report · PAY-2026-011' },
  { label: 'Refunds', paise: -80000, source: 'Refund report · REF-2026-011' },
  { label: 'Chargeback', paise: -35000, source: 'Disputed payment · DSP-2026-011' },
];
export const expected = breakdown.reduce((sum, row) => sum + row.paise, 0);
export const received = 1840000;
export const missing = expected - received;
export const money = (paise: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(paise / 100);
export const audience = Array.from({ length: 200 }, (_, index) => ({
  id: index + 1,
  daysSinceVisit: index < 130 ? 40 : 10,
  consent: index < 120,
})).filter((customer) => customer.daysSinceVisit >= 30 && customer.consent);
export const initialOffer =
  'We miss you at Sharma General Store! Show this message on your next visit for 10% off your purchase this week.';
export type Intent = 'payment' | 'campaign' | 'bank' | 'sales' | 'other';
export type Action = 'confirm' | 'pending' | 'verified';
export type Turn = {
  id: string;
  question: string;
  intent: Intent;
  started: number;
  offer: string;
  action?: Action;
  approvedAt?: number;
  replyText?: string;
  salesPeriod?: { start: string; end: string };
  salesMode?: 'today' | 'date' | 'month' | 'range';
  reportRequestedAt?: number;
};
export function detectIntent(question: string): Intent {
  if (/sales|statement|revenue|बिक्री|रिपोर्ट|అమ్మక|నివేదిక/i.test(question)) return 'sales';
  if (/bank account|account details|ifsc|बैंक खाता|बैंक अकाउंट|బ్యాంకు|బ్యాంక్/i.test(question))
    return 'bank';
  if (
    /customer|win.back|offer|campaign|come back|promot|ग्राहक|ऑफर|छूट|కస్టమర్|వినియోగదార|ఆఫర్|ఆఫర|తగ్గింపు/i.test(
      question,
    )
  )
    return 'campaign';
  if (
    /settle|payment|short|credited|credit|refund|transaction|received|payout|deposit|18[, ]?400|भुगतान|पैसे|पैसा|रिफंड|लेनदेन|चెల్లింపు|చెల్లింప|డబ్బు|జమ|రిఫండ్/i.test(
      question,
    )
  )
    return 'payment';
  return 'other';
}
export function readFollowup(turn: Turn) {
  const freshBankRecord = { id: 'BANK-FOLLOWUP-012', paise: 16680 };
  return turn.action === 'pending' && freshBankRecord.paise === missing ? freshBankRecord : null;
}
export function readDelivery(turn: Turn) {
  if (turn.intent !== 'campaign' || !turn.approvedAt) return null;
  const receipts = audience.map((customer) => ({ delivered: customer.id % 60 !== 0 }));
  const delivered = receipts.filter((receipt) => receipt.delivered).length;
  return { delivered, failed: receipts.length - delivered };
}
export function loadTurns(): Turn[] {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem('bizmate-demo-v1') ?? '[]');
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}
