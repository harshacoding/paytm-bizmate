import type { Turn } from './demo';

export function amountFromQuestion(question: string) {
  const match = question.match(/(?:₹|rs\.?|rupees?|paid|refunded)\s*(\d[\d,]*(?:\.\d{1,2})?)/i);
  return match ? paiseFromInput(match[1].replaceAll(',', '')) : undefined;
}

export function paiseFromInput(value: string) {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return undefined;
  const [whole, fraction = ''] = value.split('.');
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : undefined;
}

export const counterPayments = [
  { id: 'PAY-480-001', paise: 48000, minutesAgo: 10, status: 'Received' },
  { id: 'PAY-480-002', paise: 48000, minutesAgo: 45, status: 'Received' },
  { id: 'PAY-950-001', paise: 95000, minutesAgo: 6, status: 'Pending' },
] as const;

export function findCounterPayments(amount: number, minutes: number, settled = false) {
  return counterPayments
    .filter((record) => record.paise === amount && record.minutesAgo <= minutes)
    .map((record) => ({ ...record, status: settled ? 'Received' : record.status }));
}

export const existingRefund = {
  id: 'RF-650-001',
  paymentId: 'PAY-650-001',
  amount: 65000,
  bankReference: 'DEMO-ARN-650-001',
};
export const closingSummary = { collections: 2000000, refunds: 65000, bankTransfers: 1840000 };

export function readRefundFollowup(turn: Turn) {
  if (
    !turn.approvedAt ||
    turn.action !== 'pending' ||
    turn.refundQuery?.amount !== existingRefund.amount
  )
    return null;
  return {
    refundId: existingRefund.id,
    amount: existingRefund.amount,
    status: 'credited',
    source: 'RF-FOLLOWUP-650-001',
  };
}
