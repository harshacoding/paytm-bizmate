import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { speechLocales, translate } from '../i18n';
import type { Language } from '../i18n';

beforeEach(() => {
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
  fireEvent.click(screen.getByRole('button', { name }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
}

it('reviews simulated speech before sending, then verifies the credit after approval', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Simulate dictation' }));
  tick(950);
  const draft = screen.getByRole('textbox', { name: 'Type a question' });
  expect(draft).toHaveValue('Why is my');
  expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  tick(1200);
  fireEvent.click(screen.getByRole('button', { name: 'Done' }));
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

it('preserves the draft if speech is unavailable and keeps bank changes pending', () => {
  render(<App />);
  const draft = screen.getByRole('textbox', { name: 'Type a question' });
  fireEvent.change(draft, { target: { value: 'My draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Speak' }));
  expect(draft).toHaveValue('My draft');
  expect(screen.getByText('You can still type your question.')).toBeInTheDocument();
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
  tick(7000);
  fireEvent.click(screen.getByRole('button', { name: 'Explain the deductions' }));
  expect(screen.getByText(/In this sample, sales of/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Type a question' }), {
    target: { value: 'when can I check?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  expect(screen.getByText(/The demo uses one sample payment period/)).toBeInTheDocument();
  expect(screen.getAllByRole('progressbar')).toHaveLength(1);
});

it.each(['en', 'hi', 'te'] as Language[])(
  'runs editable simulated dictation and support approval in %s',
  (language) => {
    const view = render(<App />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: language } });
    const t = (text: string) => translate(text, language);
    expect(document.documentElement.lang).toBe(language);
    fireEvent.click(screen.getByRole('button', { name: t('Simulate dictation') }));
    tick(6000);
    expect(screen.getByRole('combobox')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: t('Done') }));
    expect(screen.getByRole('textbox', { name: t('Type a question') })).toHaveValue(
      t('Why is my payment short?'),
    );
    expect(screen.queryByRole('progressbar')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: t('Send') }));
    tick(7000);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
    fireEvent.click(screen.getByRole('button', { name: t('Ask support') }));
    fireEvent.click(screen.getByRole('button', { name: t('Confirm support request') }));
    expect(screen.getByText(t('Pending with support.'))).toBeInTheDocument();
    view.unmount();
    render(<App />);
    expect(screen.getByRole('combobox')).toHaveValue(language);
  },
);

it.each(['en', 'hi', 'te'] as Language[])(
  'configures browser speech recognition and keeps failed drafts in %s',
  (language) => {
    let recognition: MockRecognition;
    class MockRecognition {
      lang = '';
      onresult?: (event: { results: { transcript: string }[][] }) => void;
      onerror?: () => void;
      start() {
        recognition = this;
      }
      abort() {}
    }
    vi.stubGlobal('SpeechRecognition', MockRecognition);
    render(<App />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: language } });
    const t = (text: string) => translate(text, language);
    const draft = screen.getByRole('textbox', { name: t('Type a question') });
    fireEvent.change(draft, { target: { value: 'Existing draft' } });
    fireEvent.click(screen.getByRole('button', { name: t('Speak') }));
    expect(recognition!.lang).toBe(speechLocales[language]);
    act(() =>
      recognition!.onresult?.({ results: [[{ transcript: t('Why is my payment short?') }]] }),
    );
    expect(draft).toHaveValue('Existing draft ' + t('Why is my payment short?'));
    act(() => recognition!.onerror?.());
    expect(draft).toHaveValue('Existing draft');
    expect(screen.getByText(t('You can still type your question.'))).toBeInTheDocument();
  },
);
