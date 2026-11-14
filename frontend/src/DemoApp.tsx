import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { BarVisualizer } from './components/elevenlabs/bar-visualizer';
import {
  ResponseActivity,
  activityState,
  responseDuration,
  replyDelay,
  followupDelay,
} from './components/ResponseActivity';
import { Waveform, StaticWaveform } from './components/elevenlabs/waveform';
import {
  audience,
  breakdown,
  detectIntent,
  expected,
  initialOffer,
  missing,
  money,
  questions,
  moreQuestions,
  readDelivery,
  readFollowup,
  received,
  stages,
} from './demo';
import type { Turn } from './demo';
import { useDictation } from './useDictation';
import { useChats } from './useChats';
import { useSidebarWidth } from './useSidebarWidth';
import { LanguageProvider, useLanguage, canonical } from './i18n';
import { LanguagePicker } from './components/LanguagePicker';
import { followup, answerFollowup } from './followup';
import { SalesReport } from './components/SalesReport';
import { CounterPayment, RefundFollowup, DailyClosing } from './components/MerchantChecks';
import { amountFromQuestion } from './paymentDemo';

const symbols = {
  store:
    'M3 9l2-5h14l2 5v3a3 3 0 0 1-4 2.8A3 3 0 0 1 12 14a3 3 0 0 1-5 .8A3 3 0 0 1 3 12V9zm2 6v5h14v-5M3 9h18',
  mic: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5zm-4 6v1a7 7 0 0 0 14 0v-1m-7 8v3m-3 0h6',
  send: 'M12 20V4m-6 6l6-6 6 6',
  replay: 'M3 12a9 9 0 1 1 2 6M3 4v8h8',
  sales: 'M4 20h17M7 16v-4m5 4V8m5 8V4',
  payment: 'M3 6h18v13H3zM3 10h18m-14 5h3',
  campaign: 'M3 9v5h5l9 4V5L8 9H3zm5 5l2 6h3m7-11 2-2m-2 7 2 2',
  bank: 'M3 9h18L12 3 3 9zm2 3v6m5-6v6m4-6v6m5-6v6M3 21h18',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
} as const;

export function Icon({ name, size = 19 }: { name: keyof typeof symbols; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={symbols[name]} />
    </svg>
  );
}

function PaymentProgress({ elapsed, reduced }: { elapsed: number; reduced: boolean }) {
  const { t } = useLanguage();
  const index = stages.filter((stage) => elapsed >= stage.at).length - 1;
  const stage = stages[index];
  const finished = stage.progress === 100;
  return (
    <section className="card">
      <div className="card-top">
        <span className="tile">
          <Icon name="payment" />
        </span>
        <h2>{finished ? t('Payment check finished') : t('I’m checking your payment.')}</h2>
      </div>
      <div className="progress-status">
        <div role="status" className="progress-copy">
          {!finished && (
            <BarVisualizer
              aria-hidden="true"
              className="thinking"
              state={reduced ? undefined : activityState(elapsed, stages[3].at)}
              demo={!reduced && activityState(elapsed, stages[3].at) === 'speaking'}
              barCount={5}
              minHeight={32}
              centerAlign
            />
          )}
          {t(stage.label)}
        </div>
        <strong>{stage.progress}%</strong>
      </div>
      <div
        className="track"
        role="progressbar"
        aria-label={t('Payment check')}
        aria-valuenow={stage.progress}
        aria-valuetext={t(stage.label)}
      >
        <div
          className={finished ? 'fill' : 'fill moving'}
          style={{ width: stage.progress + '%' }}
        />
      </div>
      {index === 1 && elapsed >= 3500 && (
        <p className="delay" role="status">
          {t('The payment report is taking longer than usual.')}
        </p>
      )}
      <ol className="steps">
        {stages.slice(0, 3).map((step, i) => (
          <li key={step.at} data-current={i === index}>
            <span>{t(step.label)}</span>
            <span>{i < index ? t('Done') : i === index ? t('Checking') : t('Next')}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ChatReply({
  turn,
  now,
  reduced,
  update,
  onQuestion,
}: {
  turn: Turn;
  now: number;
  reduced: boolean;
  update: (change: Partial<Turn>) => void;
  onQuestion: (question: string) => void;
}) {
  const { t } = useLanguage();
  const elapsed = Math.max(0, now - turn.started);
  const payment = turn.intent === 'payment' && !turn.replyText;
  const campaign = turn.intent === 'campaign' && !turn.replyText;
  const delivery = readDelivery(turn);
  const reference = 'BM-' + turn.id.slice(0, 8).toUpperCase();
  const offerCost = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(audience.length * 2);
  const ask = () => update({ action: 'confirm' });
  const approve = () => update({ action: 'pending', approvedAt: Date.now() });
  if (!payment && elapsed < replyDelay) {
    return (
      <div className="reply">
        <span className="reply-avatar">
          <Icon name="store" size={15} />
        </span>
        <div className="reply-content">
          <div className="reply-name">BizMate</div>
          <ResponseActivity elapsed={elapsed} duration={replyDelay} reduced={reduced} />
        </div>
      </div>
    );
  }
  return (
    <div className="reply">
      <span className="reply-avatar">
        <Icon name="store" size={15} />
      </span>
      <div className="reply-content">
        <div className="reply-name">BizMate</div>
        {turn.intent === 'sales' && (
          <SalesReport turn={turn} now={now} reduced={reduced} update={update} />
        )}
        {!turn.replyText && turn.intent === 'counter' && (
          <CounterPayment turn={turn} now={now} reduced={reduced} update={update} />
        )}
        {!turn.replyText && turn.intent === 'refund' && (
          <RefundFollowup turn={turn} now={now} reduced={reduced} update={update} />
        )}
        {!turn.replyText && turn.intent === 'closing' && (
          <DailyClosing turn={turn} onQuestion={onQuestion} />
        )}
        {turn.replyText && (
          <section className="card">
            <p>{t(turn.replyText)}</p>
          </section>
        )}
        {payment && (
          <>
            <PaymentProgress elapsed={elapsed} reduced={reduced} />
            {elapsed >= stages[3].at && (
              <section className="card">
                <h2>
                  {money(missing)} {t('is still missing')}
                </h2>
                <p>
                  {t('I compared your sales and deductions with the amount your bank received.')}
                </p>
                <dl className="totals">
                  <div>
                    <dt>{t('Expected')}</dt>
                    <dd>{money(expected)}</dd>
                  </div>
                  <div>
                    <dt>{t('Received')}</dt>
                    <dd>{money(received)}</dd>
                  </div>
                </dl>
                <details>
                  <summary>
                    {t('View details')}
                    <span>{t('· Payment breakdown')}</span>
                  </summary>
                  <dl className="breakdown">
                    {breakdown.map((row) => (
                      <div key={t(row.label)}>
                        <dt>
                          {t(row.label)}
                          <small>{row.source}</small>
                        </dt>
                        <dd>{money(row.paise)}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="fine">Sample bank record · BANK-2026-011</p>
                </details>
                {!turn.action && (
                  <button type="button" className="primary" onClick={ask}>
                    {t('Ask support')}
                  </button>
                )}
              </section>
            )}
          </>
        )}
        {campaign && (
          <section className="card">
            <h2>{t('Bring customers back')}</h2>
            <p>
              <strong>
                {audience.length} {t('customers who agreed to receive offers')}
              </strong>{' '}
              {t('haven’t visited in 30 days or more. The estimated cost is')}{' '}
              <strong>{offerCost}</strong>.
            </p>
            <label className="offer-label" htmlFor={reference}>
              {t('Offer message')}
            </label>
            <textarea
              id={reference}
              className="offer"
              value={turn.offer}
              readOnly={!!turn.action}
              onChange={(event) => update({ offer: event.target.value })}
            />
            {!turn.action && (
              <button type="button" className="primary" disabled={!turn.offer.trim()} onClick={ask}>
                {t('Review simulated send')}
              </button>
            )}
          </section>
        )}
        {turn.intent === 'bank' && !turn.replyText && (
          <section className="card">
            <h2>{t('Change your bank account')}</h2>
            <p>
              {t(
                'Merchant support can help you change the bank account where you receive payments. I can prepare a support request for you.',
              )}
            </p>
            {!turn.action && (
              <button type="button" className="primary" onClick={ask}>
                {t('Ask support')}
              </button>
            )}
          </section>
        )}
        {turn.intent === 'other' && (
          <section className="card">
            <p>
              {t(
                'I can check a short payment, prepare a customer offer, or put you in touch with support for a bank account change. Which would you like help with?',
              )}
            </p>
          </section>
        )}
        {turn.action === 'confirm' && turn.intent !== 'refund' && (
          <section className="card confirmation">
            <h2>{campaign ? t('Send this offer?') : t('Create a support request?')}</h2>
            <p>
              {campaign
                ? t('Simulate sending the offer above to ') +
                  audience.length +
                  t(' customers at an estimated cost of ') +
                  offerCost +
                  '.'
                : payment
                  ? t(
                      'Share the payment breakdown and missing amount with simulated merchant support.',
                    )
                  : t('Ask simulated merchant support to help change your bank account.')}
            </p>
            <div className="actions">
              <button type="button" className="primary" onClick={approve}>
                {campaign ? t('Confirm simulated send') : t('Confirm support request')}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => update({ action: undefined })}
              >
                {t('Cancel')}
              </button>
            </div>
          </section>
        )}
        {turn.approvedAt && campaign && delivery && (
          <section className="card outcome">
            <h2>{t('Simulated delivery checked')}</h2>
            <p role="status">
              <strong>
                {delivery.delivered} {t('delivered,')} {delivery.failed} {t('failed')}
              </strong>
            </p>
          </section>
        )}
        {turn.approvedAt && !campaign && turn.intent !== 'refund' && (
          <section className="card outcome">
            <h2>
              {turn.action === 'verified'
                ? t('Missing credit verified')
                : t('Support request created')}
            </h2>
            <p role="status">
              {turn.action === 'verified'
                ? money(missing) + t(' arrived in a fresh sample bank record. The issue is closed.')
                : t('Pending with support.')}
            </p>
            {payment && turn.action === 'pending' && (
              <>
                <p className="fine">{t('Follow-up scheduled for tomorrow in the demo.')}</p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    if (readFollowup(turn)) update({ action: 'verified' });
                  }}
                >
                  {t('Run simulated follow-up')}
                </button>
              </>
            )}
            <details>
              <summary>
                {t('View details')}
                <span>{t('· Ticket reference')}</span>
              </summary>
              <p>
                {t('Simulated ticket')}
                <strong>{reference}</strong>
              </p>
              {turn.action === 'verified' && <p>Follow-up bank record · BANK-FOLLOWUP-012</p>}
            </details>
          </section>
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <MerchantApp />
    </LanguageProvider>
  );
}

function MerchantApp() {
  const { language, t } = useLanguage();
  const { chats, activeId, turns, draft, setTurns, setDraft, newChat, selectChat } = useChats();
  const activeChat = chats.find((item) => item.id === activeId)!;
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const sidebar = useSidebarWidth();
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      const saved = localStorage.getItem('bizmate-theme');
      if (saved === 'light' || saved === 'dark') return saved;
    } catch {}
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('bizmate-theme', theme);
    } catch {}
  }, [theme]);
  const [now, setNow] = useState(Date.now);
  const [announcement, announce] = useState('');
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  const input = useRef<HTMLTextAreaElement>(null);
  const chat = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    if (!input.current) return;
    input.current.style.height = 'auto';
    input.current.style.height = Math.min(input.current.scrollHeight, 120) + 'px';
  }, [draft, activeId, language]);
  const focusComposer = () => window.requestAnimationFrame(() => input.current?.focus());
  const voice = useDictation(draft, setDraft, focusComposer);
  const working = turns.some(
    (turn) =>
      now - turn.started < responseDuration(turn) + followupDelay ||
      (!!turn.reportRequestedAt && now - turn.reportRequestedAt < replyDelay) ||
      (!!turn.counterQuery && now - turn.counterQuery.checkedAt < replyDelay) ||
      (!!turn.refundQuery && now - turn.refundQuery.checkedAt < replyDelay),
  );

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media?.matches ?? false);
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!working) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [working]);
  useEffect(() => {
    const panel = chat.current;
    if (!panel || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      if (panel.querySelector('.welcome-wrap')) {
        panel.scrollTop = 0;
        return;
      }
      if (panel.dataset.follow !== 'false') panel.scrollTop = panel.scrollHeight;
    });
    if (panel.firstElementChild) observer.observe(panel.firstElementChild);
    return () => observer.disconnect();
  }, []);

  function sendQuestion(text: string) {
    const question = text.trim();
    if (!question || voice.mode) return;
    const started = Date.now();
    if (chat.current) chat.current.dataset.follow = 'true';
    setNow(started);
    const previousTurn = turns[turns.length - 1];
    const detected = detectIntent(canonical(question));
    const contextual =
      previousTurn &&
      previousTurn.intent !== 'other' &&
      (detected === 'other' ||
        (detected === previousTurn.intent &&
          followup(previousTurn.intent).options.includes(canonical(question))));
    const intent = contextual ? previousTurn.intent : detected;
    const requestedAmount = amountFromQuestion(question);
    const replyText =
      contextual && intent !== 'sales' && !(intent === 'counter' && requestedAmount)
        ? answerFollowup(intent, canonical(question))
        : undefined;
    setTurns((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        question,
        started,
        intent,
        replyText,
        offer: t(initialOffer),
        counterQuery:
          intent === 'counter' && requestedAmount
            ? {
                amount: requestedAmount,
                minutes:
                  previousTurn?.intent === 'counter'
                    ? (previousTurn.counterQuery?.minutes ?? 15)
                    : 15,
                minMinutes:
                  previousTurn?.intent === 'counter'
                    ? previousTurn.counterQuery?.minMinutes
                    : undefined,
                checkedAt: started,
              }
            : undefined,
        refundQuery:
          intent === 'refund' && requestedAmount
            ? { amount: requestedAmount, checkedAt: started }
            : undefined,
      },
    ]);
    setDraft('');
    voice.reset();
    announce(t('Question sent.'));
    focusComposer();
  }

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendQuestion(draft);
  }

  function chatTicket(item: (typeof chats)[number]) {
    const ticket = [...item.turns]
      .reverse()
      .find(
        (turn) =>
          turn.approvedAt &&
          (turn.intent === 'payment' || turn.intent === 'bank' || turn.intent === 'refund'),
      );
    return ticket ? 'BM-' + ticket.id.slice(0, 8).toUpperCase() : '';
  }

  function chatName(item: (typeof chats)[number]) {
    const title = t(item.title ?? item.turns[0]?.question ?? 'New chat');
    const ticket = chatTicket(item);
    return ticket ? title + ' - ' + ticket : title;
  }

  function navigateChat(id?: string) {
    voice.reset();
    if (id) selectChat(id);
    else newChat();
    setNow(Date.now());
    setSidebarOpen(false);
    if (chat.current) chat.current.dataset.follow = 'true';
    focusComposer();
  }

  function replay() {
    voice.reset();
    setTurns([]);
    setDraft('');
    announce(t('Demo reset.'));
    focusComposer();
  }

  return (
    <div
      className="app-shell"
      data-resizing={sidebar.resizing}
      style={{ '--sidebar-width': sidebar.width + 'px' } as CSSProperties}
    >
      <aside
        id="chat-history"
        className={sidebarOpen ? 'history-panel open' : 'history-panel'}
        aria-label={t('Chat history')}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setSidebarOpen(false);
            document.getElementById('history-toggle')?.focus();
          }
        }}
      >
        <div className="brand">
          <span>
            <span className="paytm-logo-frame">
              <img
                className="paytm-logo"
                src="/brand/paytm.png"
                alt="Paytm"
                width="80"
                height="25"
              />
            </span>
            <span className="brand-divider" />
            <span className="bizmate-label">
              <Icon name="store" size={16} />
              BizMate
            </span>
          </span>
        </div>
        <div className="history-heading">
          <strong>{t('Chat history')}</strong>
          <button
            type="button"
            className="secondary close-history"
            onClick={() => {
              setSidebarOpen(false);
              document.getElementById('history-toggle')?.focus();
            }}
          >
            {t('Close')}
          </button>
        </div>
        <button type="button" className="primary new-chat" onClick={() => navigateChat()}>
          {t('+ New chat')}
        </button>
        <nav aria-label={t('Saved conversations')}>
          {chats.map((item) => (
            <button
              type="button"
              key={item.id}
              aria-current={item.id === activeId ? 'page' : undefined}
              onClick={() => navigateChat(item.id)}
              title={chatName(item)}
            >
              <span className="history-row">
                <span className="history-title">{chatName(item)}</span>
                {!!item.unread && (
                  <span
                    className="unread-badge"
                    aria-label={item.unread + ' ' + t('unread messages')}
                  >
                    {item.unread}
                  </span>
                )}
              </span>
            </button>
          ))}
        </nav>
        <a className="api-demo-link" href="/">
          ? {t('Back to chat')} ? {t('Sample walkthrough')}
        </a>
        <p className="history-note">{t('Chats are saved in this browser.')}</p>
        <LanguagePicker disabled={!!voice.mode} onSelect={voice.reset} />
        <button
          type="button"
          className="secondary theme-toggle"
          aria-pressed={theme === 'dark'}
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        >
          {theme === 'light' ? t('Dark theme') : t('Light theme')}
        </button>
        <div
          className="sidebar-resizer"
          role="separator"
          tabIndex={0}
          aria-label={t('Resize chat history')}
          aria-orientation="vertical"
          aria-valuemin={200}
          aria-valuemax={420}
          aria-valuenow={Math.round(sidebar.width)}
          onPointerDown={(event) => {
            event.preventDefault();
            event.currentTarget.focus();
            event.currentTarget.setPointerCapture(event.pointerId);
            sidebar.setResizing(true);
          }}
          onPointerMove={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId))
              sidebar.resize(event.clientX);
          }}
          onPointerUp={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId))
              event.currentTarget.releasePointerCapture(event.pointerId);
            sidebar.setResizing(false);
          }}
          onLostPointerCapture={() => sidebar.setResizing(false)}
          onPointerCancel={() => sidebar.setResizing(false)}
          onKeyDown={(event) => {
            if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
              event.preventDefault();
              sidebar.resize(
                event.key === 'Home'
                  ? 200
                  : event.key === 'End'
                    ? 420
                    : sidebar.width + (event.key === 'ArrowRight' ? 10 : -10),
              );
            }
          }}
        />
      </aside>
      {sidebarOpen && (
        <button
          type="button"
          className="history-backdrop"
          aria-label={t('Close chat history')}
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div className="chat-workspace">
        <header className="topbar">
          <div className="top-inner">
            <button
              id="history-toggle"
              type="button"
              className="secondary history-toggle"
              aria-controls="chat-history"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {String.fromCharCode(9776)}
              <span className="sr-only">{t('Chat history')}</span>
            </button>
            <div className="chat-title" title={chatName(activeChat)} aria-live="polite">
              <span className="chat-title-text">
                {t(activeChat.title ?? turns[0]?.question ?? 'New chat')}
              </span>
              {chatTicket(activeChat) && (
                <span className="chat-ticket">{chatTicket(activeChat)}</span>
              )}
            </div>
            <div className="header-actions">
              <span className="merchant">
                <span className="merchant-logo" aria-hidden="true">
                  <Icon name="store" size={20} />
                </span>
                <span className="merchant-name">{t('Sharma General Store')}</span>
              </span>
              <button
                className="replay"
                type="button"
                onClick={replay}
                aria-label={t('Replay demo')}
                title={t('Replay demo')}
              >
                <Icon name="replay" size={17} />
                <span>{t('Replay demo')}</span>
              </button>
            </div>
          </div>
        </header>
        <main
          className="chat"
          ref={chat}
          onScroll={(event) => {
            const panel = event.currentTarget;
            panel.dataset.follow = String(
              panel.scrollHeight - panel.clientHeight - panel.scrollTop < 72,
            );
          }}
        >
          <div className={turns.length ? 'chat-column conversation' : 'chat-column welcome-wrap'}>
            {turns.length === 0 ? (
              <section className="welcome">
                <div className="hero-mark">
                  <Icon name="store" size={35} />
                </div>
                <h1>{t('Hi! How can I help?')}</h1>
                <p>
                  {t('Ask about a payment, bring customers back, or get help with your account.')}
                </p>
                <div className="prompts">
                  {questions.map((question, index) => (
                    <button
                      key={question}
                      type="button"
                      disabled={!!voice.mode}
                      onClick={() => {
                        if (question === 'Review my sales report.') {
                          sendQuestion(t(question));
                          return;
                        }
                        setDraft(t(question));
                        focusComposer();
                      }}
                    >
                      <span className="tile">
                        <Icon
                          name={
                            (['payment', 'payment', 'replay', 'sales', 'campaign'] as const)[index]
                          }
                        />
                      </span>
                      <span>{t(question)}</span>
                      <Icon name="arrow" size={16} />
                    </button>
                  ))}
                </div>
                <details className="more-questions">
                  <summary>{t('More questions')}</summary>
                  <div className="prompts">
                    {moreQuestions.map((question) => (
                      <button
                        type="button"
                        key={question}
                        disabled={!!voice.mode}
                        onClick={() => {
                          if (question === 'Review my sales report.') {
                            sendQuestion(t(question));
                          } else {
                            setDraft(t(question));
                            focusComposer();
                          }
                        }}
                      >
                        <span className="tile">
                          <Icon name={question === 'Review my sales report.' ? 'sales' : 'bank'} />
                        </span>
                        <span>{t(question)}</span>
                        <Icon name="arrow" size={16} />
                      </button>
                    ))}
                  </div>
                </details>
              </section>
            ) : (
              turns.map((turn) => (
                <article className="turn" key={turn.id}>
                  <div className="user-bubble">{turn.question}</div>
                  <ChatReply
                    turn={turn}
                    onQuestion={sendQuestion}
                    now={now}
                    reduced={reduced}
                    update={(change) =>
                      setTurns((previous) =>
                        previous.map((item) =>
                          item.id === turn.id ? { ...item, ...change } : item,
                        ),
                      )
                    }
                  />
                </article>
              ))
            )}
          </div>
          {!!turns.length &&
            (() => {
              const last = turns[turns.length - 1];
              if (['sales', 'counter', 'refund', 'closing'].includes(last.intent)) return null;
              const elapsed = now - last.started;
              const duration = responseDuration(last);
              if (elapsed < duration) return null;
              if (elapsed < duration + followupDelay)
                return (
                  <div className="chat-column followup">
                    <ResponseActivity
                      elapsed={elapsed - duration}
                      duration={followupDelay}
                      reduced={reduced}
                      followup
                    />
                  </div>
                );
              const prompt = followup(last.intent);
              return (
                <section className="chat-column followup" aria-label={t('Follow-up questions')}>
                  <h2>{t(prompt.question)}</h2>
                  <div className="followup-options">
                    {prompt.options.map((option) => (
                      <button
                        type="button"
                        className="secondary"
                        key={t(option)}
                        disabled={!!voice.mode}
                        onClick={() => sendQuestion(t(option))}
                      >
                        {t(option)}
                      </button>
                    ))}
                  </div>
                  <p>{t('Choose an option, or type your answer below.')}</p>
                </section>
              );
            })()}
        </main>
        <footer className="composer-region">
          <div className="chat-column">
            <form className="composer" onSubmit={send}>
              {voice.mode && (
                <div className="listening">
                  <span className="listening-label" role="status">
                    {t(
                      voice.mode === 'loading'
                        ? 'Preparing voice input…'
                        : voice.mode === 'processing'
                          ? 'Finishing transcription…'
                          : 'Listening…',
                    )}
                  </span>
                  <div className="wave" aria-hidden="true">
                    {reduced ? (
                      <StaticWaveform bars={27} height={27} barColor="#007da5" />
                    ) : (
                      <Waveform
                        data={voice.waveform}
                        active={voice.mode === 'mic'}
                        height={27}
                        barWidth={3}
                        barGap={3}
                        barColor="#007da5"
                      />
                    )}
                  </div>
                  <button type="button" className="secondary" onClick={() => voice.end(true)}>
                    {t('Cancel')}
                  </button>
                  <button
                    type="button"
                    className="primary"
                    disabled={voice.mode !== 'mic'}
                    onClick={() => void voice.end()}
                  >
                    {t('Done')}
                  </button>
                </div>
              )}
              <div className="composer-input">
                <label className="sr-only" htmlFor="question">
                  {t('Type a question')}
                </label>
                <textarea
                  id="question"
                  ref={input}
                  rows={1}
                  maxLength={2000}
                  placeholder={t('Type a question…')}
                  value={draft}
                  readOnly={!!voice.mode}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <div className="composer-actions">
                  <button
                    type="button"
                    className="secondary speak"
                    aria-label={t('Speak')}
                    title={t('Speak')}
                    disabled={!!voice.mode}
                    onClick={() => voice.start()}
                  >
                    <Icon name="mic" size={16} />
                  </button>
                  <button
                    type="submit"
                    className="primary send"
                    aria-label={t('Send')}
                    disabled={!draft.trim() || !!voice.mode}
                  >
                    <Icon name="send" size={18} />
                    <span className="send-label" aria-hidden="true">
                      {t('Send')}
                    </span>
                  </button>
                </div>
              </div>
            </form>
            <div className="notice" role="status">
              {voice.notice}
            </div>
            <p className="demo-note">
              <span />
              {t('Demo mode · Sample data and simulated actions')}
            </p>
            <div className="sr-only" role="status">
              {announcement}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
