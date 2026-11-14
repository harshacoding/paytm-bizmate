import type { Turn } from './demo';

export function amountFromQuestion(question: string) {
  const match =
    question.match(/(?:₹|rs\.?|rupees?|paid|refunded)\s*(\d[\d,]*(?:\.\d{1,2})?)/i) ??
    question.match(/^\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(?:rupees?|rs\.?|रुपये|రూపాయలు)?\s*[?]?\s*$/i);
  return match ? paiseFromInput(match[1].replaceAll(',', '')) : undefined;
}

export function paiseFromInput(value: string) {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return undefined;
  const [whole, fraction = ''] = value.split('.');
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : undefined;
}

export const counterPayments = [
  { id: 'PAY-100-001', paise: 10000, payerName: 'Saiteja', minutesAgo: 7, status: 'Received' },
  { id: 'PAY-100-002', paise: 10000, payerName: 'Ravi', minutesAgo: 9, status: 'Pending' },
  { id: 'PAY-100-003', paise: 10000, payerName: 'Neha', minutesAgo: 3, status: 'Received' },
  { id: 'PAY-100-004', paise: 10000, payerName: null, minutesAgo: 13, status: 'Received' },
  { id: 'PAY-480-001', paise: 48000, payerName: 'Saiteja', minutesAgo: 10, status: 'Received' },
  { id: 'PAY-480-002', paise: 48000, payerName: 'Ramesh', minutesAgo: 45, status: 'Received' },
  { id: 'PAY-950-001', paise: 95000, payerName: 'Anitha', minutesAgo: 6, status: 'Pending' },
] as const;

export function findCounterPayments(
  amount: number,
  minutes: number,
  settled = false,
  options: { minMinutes?: number; payerName?: string; settledIds?: readonly string[] } = {},
) {
  const payer = options.payerName?.trim().normalize('NFKC').toLocaleLowerCase();
  return counterPayments
    .filter(
      (record) =>
        record.paise === amount &&
        record.minutesAgo <= minutes &&
        record.minutesAgo >= (options.minMinutes ?? 0) &&
        (!payer || record.payerName?.normalize('NFKC').toLocaleLowerCase().includes(payer)),
    )
    .sort((a, b) => a.minutesAgo - b.minutesAgo)
    .map((record) => ({
      ...record,
      status: settled || options.settledIds?.includes(record.id) ? 'Received' : record.status,
    }));
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
