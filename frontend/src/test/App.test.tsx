import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../DemoApp';
import { languages, speechLocales, translate } from '../i18n';
import type { Language } from '../i18n';
import { detectIntent } from '../demo';
import { merchantToday, sampleSales, validPeriod } from '../components/SalesReport';
import { prepareVoiceInput, openVoiceStream } from '../voiceEngine';
import { captureVoice } from '../voiceCapture';
import { findCounterPayments } from '../paymentDemo';
const translateLanguage = (language: Language) => languages[language];
vi.mock('../voiceEngine', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../voiceEngine')>()),
  prepareVoiceInput: vi.fn(),
  openVoiceStream: vi.fn(),
}));
vi.mock('../voiceCapture', () => ({ captureVoice: vi.fn() }));
let samples: (audio: Float32Array) => void;
let transcript: (text: string) => void;
const mockSend = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(prepareVoiceInput).mockResolvedValue(undefined);
  vi.mocked(openVoiceStream).mockImplementation(async (onText) => {
    transcript = onText;
    return { sendAudio: mockSend, finish: vi.fn().mockResolvedValue(''), cancel: vi.fn() };
  });
  mockSend.mockImplementation(() => transcript('Why is my payment short?'));
  vi.mocked(captureVoice).mockImplementation(async (callback) => {
    samples = callback;
    return { sampleRate: 16000, stop: vi.fn().mockResolvedValue(undefined) };
  });
  localStorage.clear();
  localStorage.setItem('bizmate-theme', 'light');
  vi.useFakeTimers();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener() {},
    removeEventListener() {},
  }));
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function tick(ms: number) {
  act(() => vi.advanceTimersByTime(ms));
}

function choose(name: string) {
  if (name === 'How do I change my bank account?')
    fireEvent.click(screen.getByText('More questions'));
  fireEvent.click(screen.getByRole('button', { name }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  tick(3400);
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

it('reviews live speech before sending, then verifies the credit after approval', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Speak' }));
  await flush();
  mockSend.mockImplementationOnce(() => transcript('Why is my'));
  act(() => samples(new Float32Array(16000).fill(0.1)));
  await flush(3000);

  const draft = screen.getByRole('textbox', { name: 'Type a question' });
  expect(draft).toHaveValue('Why is my');
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  mockSend.mockImplementationOnce(() => transcript('Why is my payment short?'));
  act(() => samples(new Float32Array(16000).fill(0.1)));
  await flush(3000);
  fireEvent.click(screen.getByRole('button', { name: 'Done' }));
  await flush();
  expect(draft).toHaveValue('Why is my payment short?');
  expect(screen.queryByRole('progressbar')).toBeNull();
  fireEvent.change(draft, { target: { value: 'Why is my settlement short?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20');
  tick(3600);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '60');
  expect(screen.getByText('The payment report is taking longer than usual.')).toBeInTheDocument();
  tick(1500);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '90');
  tick(1900);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
  expect(screen.getByText('₹166.80 is still missing')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ask support' }));
  expect(screen.queryByText('Pending with support.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm support request' }));
  expect(screen.getByText('Pending with support.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Run simulated follow-up' }));
  expect(screen.getByText('Missing credit verified')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Replay demo' }));
  expect(screen.getByRole('heading', { name: 'Hi! How can I help?' })).toBeInTheDocument();
});

it('shows campaign delivery only after confirmation', () => {
  render(<App />);
  choose('Help me bring customers back.');
  fireEvent.change(screen.getByRole('textbox', { name: 'Offer message' }), {
    target: { value: 'Save 10% today.' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Review simulated send' }));
  expect(screen.queryByText('118 delivered, 2 failed')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm simulated send' }));
  expect(screen.getByText('118 delivered, 2 failed')).toBeInTheDocument();
});

it('preserves the draft if speech is unavailable and keeps bank changes pending', async () => {
  vi.mocked(prepareVoiceInput).mockRejectedValueOnce(new Error('unavailable'));
  render(<App />);
  const draft = screen.getByRole('textbox', { name: 'Type a question' });
  fireEvent.change(draft, { target: { value: 'My draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Speak' }));
  await flush();
  expect(draft).toHaveValue('My draft');
  expect(
    screen.getByText('Voice input is unavailable. You can still type your question.'),
  ).toBeInTheDocument();
  choose('How do I change my bank account?');
  fireEvent.click(screen.getByRole('button', { name: 'Ask support' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm support request' }));
  expect(screen.getByText('Pending with support.')).toBeInTheDocument();
});

it('keeps separate chat drafts, restores history and persists the theme', () => {
  const view = render(<App />);
  choose('Help me bring customers back.');
  const draft = screen.getByRole('textbox', { name: 'Type a question' });
  fireEvent.change(draft, { target: { value: 'First chat draft' } });
  fireEvent.click(screen.getByRole('button', { name: /New chat/ }));
  expect(draft).toHaveValue('');
  fireEvent.change(draft, { target: { value: 'Second chat draft' } });
  const history = screen.getByRole('navigation', { name: 'Saved conversations' });
  fireEvent.click(history.querySelectorAll('button')[1]);
  expect(draft).toHaveValue('First chat draft');
  expect(screen.getByRole('textbox', { name: 'Offer message' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Dark theme/ }));
  expect(document.documentElement.dataset.theme).toBe('dark');
  view.unmount();
  render(<App />);
  expect(screen.getByRole('textbox', { name: 'Type a question' })).toHaveValue('First chat draft');
  expect(screen.getByRole('button', { name: /Light theme/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});

it('accepts suggested and typed follow-up replies in context', () => {
  render(<App />);
  choose('Why is my payment short?');
  tick(8200);
  fireEvent.click(screen.getByRole('button', { name: 'Explain the deductions' }));
  expect(screen.getByText(/Connecting/)).toBeInTheDocument();
  tick(2200);
  expect(screen.getByText(/In this sample, sales of/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Type a question' }), {
    target: { value: 'when can I check?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  tick(2200);
  expect(screen.getByText(/The demo uses one sample payment period/)).toBeInTheDocument();
  expect(screen.getAllByRole('progressbar')).toHaveLength(1);
});

it('shows response activity before answers and before follow-up questions', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Help me bring customers back.' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  expect(screen.getByText('Connecting…')).toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'Offer message' })).toBeNull();
  tick(500);
  expect(screen.getByText('Thinking…')).toBeInTheDocument();
  tick(1200);
  expect(screen.getByText('Preparing your reply…')).toBeInTheDocument();
  tick(500);
  expect(screen.getByRole('textbox', { name: 'Offer message' })).toBeInTheDocument();
  expect(screen.queryByText('What kind of offer would suit your customers?')).toBeNull();
  expect(screen.getByText('Connecting…')).toBeInTheDocument();
  tick(1000);
  expect(screen.getByText('Preparing a follow-up question…')).toBeInTheDocument();
  tick(200);
  expect(screen.getByText('What kind of offer would suit your customers?')).toBeInTheDocument();
  expect(screen.queryByText('Thinking…')).toBeNull();
});

it('opens the sales period picker and generates reports for dates, months and ranges', () => {
  render(<App />);
  fireEvent.click(screen.getByText('More questions'));
  fireEvent.click(screen.getByRole('button', { name: 'Review my sales report.' }));
  tick(2200);
  expect(screen.getByRole('radio', { name: 'Today' })).toBeChecked();
  fireEvent.click(screen.getByRole('button', { name: 'View sales report' }));
  expect(screen.queryByText('Your sample sales report')).toBeNull();
  tick(2200);
  expect(screen.getByText('Your sample sales report')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: 'Select date' }));
  const date = screen.getByLabelText('Select date', { selector: 'input[type="date"]' });
  expect(date).toHaveAttribute('max', merchantToday());
  fireEvent.change(date, { target: { value: '2025-11-12' } });
  fireEvent.click(screen.getByRole('button', { name: 'View sales report' }));
  tick(2200);
  expect(screen.getByText('12 Nov 2025 — 12 Nov 2025')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: 'Monthly' }));
  fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2024' } });
  fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'View sales report' }));
  tick(2200);
  expect(screen.getByText('1 Feb 2024 — 29 Feb 2024')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: 'Date range' }));
  fireEvent.change(screen.getByLabelText('From date'), { target: { value: '2025-11-12' } });
  fireEvent.change(screen.getByLabelText('To date'), { target: { value: '2025-11-11' } });
  fireEvent.click(screen.getByRole('button', { name: 'View sales report' }));
  expect(screen.getByRole('alert')).toHaveTextContent('The start date must come first.');
  fireEvent.change(screen.getByLabelText('To date'), { target: { value: '2025-11-13' } });
  fireEvent.click(screen.getByRole('button', { name: 'View sales report' }));
  tick(2200);
  expect(screen.getByText('12 Nov 2025 — 13 Nov 2025')).toBeInTheDocument();
});

it('aggregates inclusive sales periods exactly and rejects future or invalid dates', () => {
  const first = sampleSales({ start: '2025-11-12', end: '2025-11-12' });
  const second = sampleSales({ start: '2025-11-13', end: '2025-11-13' });
  const both = sampleSales({ start: '2025-11-12', end: '2025-11-13' });
  expect(both.gross).toBe(first.gross + second.gross);
  expect(both.payments).toBe(first.payments + second.payments);
  expect(both.upi + both.cards + both.cash).toBe(both.gross);
  expect(both.net).toBe(both.gross - both.refunds);
  expect(validPeriod({ start: '2025-02-29', end: '2025-03-01' }, '2026-11-14')).toBe(false);
  expect(validPeriod({ start: '2026-11-15', end: '2026-11-15' }, '2026-11-14')).toBe(false);
});

it('opens the language picker upward and supports keyboard selection and dismissal', () => {
  render(<App />);
  const trigger = screen.getByRole('button', { name: 'Language: English' });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: 'ArrowUp' });
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  const english = screen.getByRole('menuitemradio', { name: 'English' });
  expect(english).toHaveFocus();
  fireEvent.keyDown(english, { key: 'End' });
  const telugu = screen.getByRole('menuitemradio', { name: /Telugu/ });
  expect(telugu).toHaveFocus();
  fireEvent.keyDown(telugu, { key: 'Escape' });
  expect(trigger).toHaveFocus();
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole('menuitemradio', { name: /Hindi/ }));
  expect(localStorage.getItem('bizmate-language')).toBe('hi');
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  fireEvent.pointerDown(document.body);
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
});

it.each(['en', 'hi', 'te'] as Language[])(
  'keeps replies in %s regardless of the spoken language',
  async (language) => {
    const view = render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /^Language:/ }));
    fireEvent.click(
      screen.getByRole('menuitemradio', { name: new RegExp(translateLanguage(language)) }),
    );
    const t = (text: string) => translate(text, language);
    const inputLanguage = language === 'en' ? 'hi' : language === 'hi' ? 'te' : 'en';
    const spoken = translate('Why is my payment short?', inputLanguage);
    mockSend.mockImplementation(() => transcript(spoken));
    fireEvent.click(screen.getByRole('button', { name: t('Speak') }));
    await flush();
    act(() => samples(new Float32Array(16000).fill(0.1)));
    await flush(3000);
    expect(
      screen.getByRole('button', { name: `${t('Language')}: ${translateLanguage(language)}` }),
    ).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: t('Type a question') })).toHaveValue(spoken);
    fireEvent.click(screen.getByRole('button', { name: t('Done') }));
    await flush();
    expect(screen.queryByRole('progressbar')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: t('Send') }));
    tick(7000);
    expect(screen.getByText(t('Expected'))).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: t('Ask support') }));
    fireEvent.click(screen.getByRole('button', { name: t('Confirm support request') }));
    expect(screen.getByText(t('Pending with support.'))).toBeInTheDocument();
    view.unmount();
    render(<App />);
    expect(
      screen.getByRole('button', { name: `${t('Language')}: ${translateLanguage(language)}` }),
    ).toBeInTheDocument();
  },
);

it.each(['en', 'hi', 'te'] as Language[])(
  'preserves the draft after a transcription failure in %s',
  async (language) => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /^Language:/ }));
    fireEvent.click(
      screen.getByRole('menuitemradio', { name: new RegExp(translateLanguage(language)) }),
    );
    const t = (text: string) => translate(text, language);
    const draft = screen.getByRole('textbox', { name: t('Type a question') });
    fireEvent.change(draft, { target: { value: 'Existing draft' } });
    mockSend.mockImplementationOnce(() => {
      throw new Error('unavailable');
    });
    fireEvent.click(screen.getByRole('button', { name: t('Speak') }));
    await flush();
    act(() => samples(new Float32Array(16000).fill(0.1)));
    await flush(3000);
    expect(draft).toHaveValue('Existing draft');
    expect(
      screen.getByText(t('Voice input is unavailable. You can still type your question.')),
    ).toBeInTheDocument();
  },
);

it('keeps a cancelled voice connection from opening the microphone', async () => {
  let ready: () => void = () => {};
  vi.mocked(prepareVoiceInput).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        ready = resolve;
      }),
  );
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Speak' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  ready();
  await flush();
  expect(captureVoice).not.toHaveBeenCalled();
  expect(screen.getByRole('textbox', { name: 'Type a question' })).toHaveValue('');
});

it('clears the sample unread badge when the conversation is opened', () => {
  render(<App />);
  expect(screen.getByLabelText('1 unread messages')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Sales report update/ }));
  expect(screen.queryByLabelText('1 unread messages')).toBeNull();
  expect(screen.getByText('Your sample sales report')).toBeInTheDocument();
});

it('counts replies that finish while another chat is open and clears them when read', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Help me bring customers back.' }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  fireEvent.click(screen.getByRole('button', { name: /New chat/ }));
  tick(3500);
  expect(screen.getByLabelText('2 unread messages')).toHaveTextContent('2');
  const history = within(screen.getByRole('navigation', { name: 'Saved conversations' }));
  fireEvent.click(history.getByRole('button', { name: /Help me bring customers back/ }));
  expect(screen.queryByLabelText('2 unread messages')).toBeNull();
});

it('resizes chat history with the keyboard and saves the width', () => {
  const view = render(<App />);
  const handle = screen.getByRole('separator', { name: 'Resize chat history' });
  fireEvent.keyDown(handle, { key: 'ArrowRight' });
  expect(handle).toHaveAttribute('aria-valuenow', '242');
  view.unmount();
  render(<App />);
  expect(screen.getByRole('separator', { name: 'Resize chat history' })).toHaveAttribute(
    'aria-valuenow',
    '242',
  );
});

it('keeps branding in history and updates the current chat title with an approved ticket', () => {
  const view = render(<App />);
  expect(within(screen.getByRole('complementary')).getByAltText('Paytm')).toBeInTheDocument();
  expect(within(screen.getByRole('banner')).queryByAltText('Paytm')).toBeNull();
  choose('How do I change my bank account?');
  const header = screen.getByRole('banner');
  expect(header).toHaveTextContent('How do I change my bank account?');
  expect(header).not.toHaveTextContent(/BM-[0-9A-F]{8}/);
  fireEvent.click(screen.getByRole('button', { name: 'Ask support' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm support request' }));
  expect(header).toHaveTextContent(/BM-[0-9A-F]{8}/);
  expect(screen.getByRole('navigation', { name: 'Saved conversations' })).not.toHaveTextContent(
    /\d+ messages?/,
  );
  view.unmount();
  render(<App />);
  expect(screen.getByRole('banner')).toHaveTextContent(/BM-[0-9A-F]{8}/);
});

it('checks counter payments by amount and time and gates Soundbox help on a confirmed match', () => {
  render(<App />);
  choose('Did I receive a payment?');
  fireEvent.change(screen.getByLabelText('Payment amount'), { target: { value: '480' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.getByText('Received', { exact: true })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Get Soundbox help' }));
  expect(screen.getByRole('link', { name: 'Paytm Soundbox help' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Payment amount'), { target: { value: '950' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.getByText('Pending', { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Get Soundbox help' })).toBeNull();
  fireEvent.change(screen.getByLabelText('Payment amount'), { target: { value: '777' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.getByText('Couldn’t find a matching payment')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Payment amount'), { target: { value: '480' } });
  fireEvent.change(screen.getByLabelText('When was it paid?'), { target: { value: '60' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(
    screen.getByText(
      'Several payments match. Compare the customer name and time, then select the right payment.',
    ),
  ).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Get Soundbox help' })).toBeNull();
});

it('checks an existing refund before approved support follow-up and verified credit', () => {
  render(<App />);
  choose('What is my refund status?');
  fireEvent.click(screen.getByRole('button', { name: 'Check existing refund' }));
  tick(2200);
  expect(screen.getByText('Refund pending')).toBeInTheDocument();
  expect(screen.getByText('RF-650-001')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Follow up on this refund' }));
  expect(screen.queryByText('Pending with support.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Confirm support request' }));
  expect(screen.getByText('Pending with support.')).toBeInTheDocument();
  expect(screen.getByRole('banner')).toHaveTextContent(/BM-[0-9A-F]{8}/);
  expect(screen.getByLabelText('Refund amount')).toHaveAttribute('readonly');
  fireEvent.click(screen.getByRole('button', { name: 'Run simulated refund update' }));
  tick(2200);
  expect(screen.getByText('Refund credited')).toBeInTheDocument();
  expect(screen.getByText('RF-650-001')).toBeInTheDocument();
});

it('disambiguates repeated ₹100 payments by payer and time without treating a pending match as received', () => {
  render(<App />);
  choose('Did I receive a payment?');
  expect(screen.getByLabelText('Payment amount')).toHaveValue(null);
  fireEvent.change(screen.getByLabelText('Payment amount'), { target: { value: '100' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.getByText('Saiteja')).toBeInTheDocument();
  expect(screen.getByText('Neha')).toBeInTheDocument();
  expect(screen.getByText('Ravi')).toBeInTheDocument();
  expect(screen.getByText('Name unavailable')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Get Soundbox help' })).toBeNull();

  fireEvent.change(screen.getByLabelText('When was it paid?'), { target: { value: '5-10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.queryByText('Neha')).toBeNull();
  expect(screen.queryByText('Name unavailable')).toBeNull();
  const saiteja = screen.getByText('Saiteja').closest<HTMLElement>('.payment-match')!;
  expect(within(saiteja).getByText(/7 minutes ago/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Select payment · Ravi/ }));
  expect(screen.queryByRole('button', { name: 'Get Soundbox help' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /Select payment · Saiteja/ }));
  expect(screen.getByRole('button', { name: 'Get Soundbox help' })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Customer name (optional)'), {
    target: { value: '  sAIteja  ' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.queryByText('Ravi')).toBeNull();
  expect(screen.getByText('Saiteja')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Customer name (optional)'), {
    target: { value: 'No matching customer' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Search payment records' }));
  tick(2200);
  expect(screen.getByText('Couldn’t find a matching payment')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Get Soundbox help' })).toBeNull();
});

it('filters inclusive time boundaries and sorts same-amount payments newest first', () => {
  expect(findCounterPayments(10000, 15).map((record) => record.minutesAgo)).toEqual([3, 7, 9, 13]);
  expect(
    findCounterPayments(10000, 7, false, { minMinutes: 7 }).map((record) => record.payerName),
  ).toEqual(['Saiteja']);
  expect(
    findCounterPayments(10000, 10, false, { minMinutes: 5 }).map((record) => record.payerName),
  ).toEqual(['Saiteja', 'Ravi']);
  expect(
    findCounterPayments(10000, 15, false, { settledIds: ['PAY-950-001'] }).find(
      (record) => record.payerName === 'Ravi',
    )?.status,
  ).toBe('Pending');
});

it.each(['en', 'hi', 'te'] as Language[])(
  'shows payment names and relative times in %s',
  (language) => {
    localStorage.setItem('bizmate-language', language);
    const t = (text: string) => translate(text, language);
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: t('Did I receive a payment?') }));
    fireEvent.click(screen.getByRole('button', { name: t('Send') }));
    tick(3400);
    fireEvent.change(screen.getByLabelText(t('Payment amount')), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: t('Search payment records') }));
    tick(2200);
    const saiteja = screen.getByText('Saiteja').closest<HTMLElement>('.payment-match')!;
    const relative = new Intl.RelativeTimeFormat(speechLocales[language], {
      numeric: 'always',
    }).format(-7, 'minute');
    expect(within(saiteja).getByText((text) => text.startsWith(relative))).toBeInTheDocument();
  },
);

it('shows separate daily collection, refund and bank-credit totals with period coverage', () => {
  render(<App />);
  choose('How much did I collect today?');
  expect(screen.getByText('Paytm collections')).toBeInTheDocument();
  expect(screen.getByText('₹20,000.00')).toBeInTheDocument();
  expect(screen.getByText('₹650.00')).toBeInTheDocument();
  expect(screen.getByText('₹18,400.00')).toBeInTheDocument();
  expect(screen.getByText(/Bank transfers can include earlier collections/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Review another sales period' }));
  tick(2200);
  expect(screen.getByRole('radio', { name: 'Monthly' })).toBeInTheDocument();
});

it('uses a follow-up amount from the chat composer to check counter payments', () => {
  render(<App />);
  choose('Did I receive a payment?');
  fireEvent.change(screen.getByRole('textbox', { name: 'Type a question' }), {
    target: { value: '100 rupees' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  tick(3400);
  expect(screen.getByText('Saiteja')).toBeInTheDocument();
  expect(screen.getByText('Ravi')).toBeInTheDocument();
  expect(screen.getByText(/7 minutes ago/)).toBeInTheDocument();
});

it.each([
  ['I took ₹20,000 yesterday. Why did only ₹18,400 reach my bank?', 'payment'],
  ['The customer says they paid ₹480, but my Soundbox didn’t speak. Did I get it?', 'counter'],
  ['I refunded ₹650. Why hasn’t my customer got it?', 'refund'],
  ['How much did I collect today, and what has reached my bank?', 'closing'],
  ['Can you bring back customers who haven’t visited in a month?', 'campaign'],
])('routes the merchant request %s', (question, intent) => {
  expect(detectIntent(question)).toBe(intent);
});
