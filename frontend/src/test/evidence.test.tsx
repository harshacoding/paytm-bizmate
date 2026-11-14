import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { SettlementEvidence } from '../components/SettlementEvidence';
import type { SettlementProof } from '../api/types';
import { paise } from '../api/format';

const line = (amount: number | null) => ({
  amount_paise: amount,
  source_references: ['source-001'],
  status: amount === null ? ('missing' as const) : ('known' as const),
  explanation: amount === null ? 'No available evidence.' : 'Confirmed synthetic source record.',
});
const proof: SettlementProof = {
  merchant_id: 'merchant_demo',
  settlement_reference: 'settlement-001',
  captured_at: '2026-11-14T07:32:53Z',
  sales: line(2000000),
  commission: line(24000),
  gst: line(4320),
  refunds: line(80000),
  chargeback: line(35000),
  expected: line(1856680),
  credit: line(1840000),
  residual: line(16680),
  sources: [],
  status: 'complete',
  warnings: [],
  simulated: true,
};
afterEach(() => vi.restoreAllMocks());

it('formats signed paise exactly through the safe-integer contract boundary', () => {
  expect(paise(9007199254740991)).toBe('₹9,00,71,99,25,47,409.91');
  expect(paise(-1)).toBe('-₹0.01');
  expect(paise(-101)).toBe('-₹1.01');
});

it('shows server financial values and source references without manufacturing task completion', async () => {
  vi.spyOn(api, 'reconcile').mockResolvedValue(proof);
  render(<SettlementEvidence language="en" allowed />);
  fireEvent.click(screen.getByRole('button', { name: 'Check source records' }));
  await screen.findByText('₹166.80');
  expect(screen.getByText('₹18,566.80')).toBeInTheDocument();
  expect(screen.getByText('₹18,400.00')).toBeInTheDocument();
  const residual = screen.getByText('Still unexplained').closest('article')!;
  fireEvent.click(within(residual).getByText('View details'));
  expect(within(residual).getByText('source-001')).toBeInTheDocument();
  expect(screen.queryByText('Goal completed')).toBeNull();
});

it('keeps missing evidence unknown and makes no zero-valued assumption', async () => {
  vi.spyOn(api, 'reconcile').mockResolvedValue({
    ...proof,
    commission: line(null),
    expected: line(null),
    residual: line(null),
    status: 'incomplete',
  });
  render(<SettlementEvidence language="en" allowed />);
  fireEvent.click(screen.getByRole('button', { name: 'Check source records' }));
  await screen.findByText('Some source records are missing');
  const commission = screen.getByText('Commission').closest('article')!;
  expect(within(commission).getByText('Unknown')).toBeInTheDocument();
  expect(within(commission).queryByText('₹0.00')).toBeNull();
});
