import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { BarVisualizer } from './components/elevenlabs/bar-visualizer';
import {
  MicrophoneWaveform,
  ScrollingWaveform,
  StaticWaveform,
} from './components/elevenlabs/waveform';
import {
  audience,
  breakdown,
  detectIntent,
  expected,
  initialOffer,
  missing,
  money,
  questions,
  readDelivery,
  readFollowup,
  received,
  stages,
} from './demo';
import type { Turn } from './demo';
import { useDictation } from './useDictation';
import { useChats } from './useChats';
import { followup, answerFollowup } from './followup';

const symbols = {
  sparkle: 'M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4L12 2z',
  store:
    'M3 9l2-5h14l2 5v3a3 3 0 0 1-4 2.8A3 3 0 0 1 12 14a3 3 0 0 1-5 .8A3 3 0 0 1 3 12V9zm2 6v5h14v-5M3 9h18',
  mic: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5zm-4 6v1a7 7 0 0 0 14 0v-1m-7 8v3m-3 0h6',
  send: 'M12 20V4m-6 6l6-6 6 6',
  replay: 'M3 12a9 9 0 1 1 2 6M3 4v8h8',
  payment: 'M3 6h18v13H3zM3 10h18m-14 5h3',
  campaign: 'M3 9v5h5l9 4V5L8 9H3zm5 5l2 6h3m7-11 2-2m-2 7 2 2',
  bank: 'M3 9h18L12 3 3 9zm2 3v6m5-6v6m4-6v6m5-6v6M3 21h18',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
} as const;

function Icon({ name, size = 19 }: { name: keyof typeof symbols; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={name === 'sparkle' ? 'currentColor' : 'none'}
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
  const index = stages.filter((stage) => elapsed >= stage.at).length - 1;
  const stage = stages[index];
  const finished = stage.progress === 100;
  return (
    <section className="card">
      <div className="card-top">
        <span className="tile">
          <Icon name="payment" />
        </span>
        <h2>{finished ? 'Payment check finished' : 'I’m checking your payment.'}</h2>
      </div>
      <div className="progress-status">
        <div role="status" className="progress-copy">
          {!finished && (
            <BarVisualizer
              aria-hidden="true"
              className="thinking"
              state={reduced ? undefined : 'thinking'}
              barCount={5}
              minHeight={32}
              centerAlign
            />
          )}
          {stage.label}
        </div>
        <strong>{stage.progress}%</strong>
      </div>
      <div
        className="track"
        role="progressbar"
        aria-label="Payment check"
        aria-valuenow={stage.progress}
        aria-valuetext={stage.label}
      >
        <div
          className={finished ? 'fill' : 'fill moving'}
          style={{ width: stage.progress + '%' }}
        />
      </div>
      {index === 1 && elapsed >= 3500 && (
        <p className="delay" role="status">
          The payment report is taking longer than usual.
        </p>
      )}
      <ol className="steps">
        {stages.slice(0, 3).map((step, i) => (
          <li key={step.at} data-current={i === index}>
            <span>{step.label}</span>
            <span>{i < index ? 'Done' : i === index ? 'Checking' : 'Next'}</span>
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
}: {
  turn: Turn;
  now: number;
  reduced: boolean;
  update: (change: Partial<Turn>) => void;
}) {
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
  return (
    <div className="reply">
      <span className="reply-avatar">
        <Icon name="sparkle" size={15} />
      </span>
      <div className="reply-content">
        <div className="reply-name">BizMate</div>
        {turn.replyText && (
          <section className="card">
            <p>{turn.replyText}</p>
          </section>
        )}
        {payment && (
          <>
            <PaymentProgress elapsed={elapsed} reduced={reduced} />
            {elapsed >= stages[3].at && (
              <section className="card">
                <h2>{money(missing)} is still missing</h2>
                <p>I compared your sales and deductions with the amount your bank received.</p>
                <dl className="totals">
                  <div>
                    <dt>Expected</dt>
                    <dd>{money(expected)}</dd>
                  </div>
                  <div>
                    <dt>Received</dt>
                    <dd>{money(received)}</dd>
                  </div>
                </dl>
                <details>
                  <summary>
                    View details <span>· Payment breakdown</span>
                  </summary>
                  <dl className="breakdown">
                    {breakdown.map((row) => (
                      <div key={row.label}>
                        <dt>
                          {row.label}
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
                    Ask support
                  </button>
                )}
              </section>
            )}
          </>
        )}
        {campaign && (
          <section className="card">
            <h2>Bring customers back</h2>
            <p>
              <strong>{audience.length} customers who agreed to receive offers</strong> haven’t
              visited in 30 days or more. The estimated cost is <strong>{offerCost}</strong>.
            </p>
            <label className="offer-label" htmlFor={reference}>
              Offer message
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
                Review simulated send
              </button>
            )}
          </section>
        )}
        {turn.intent === 'bank' && !turn.replyText && (
          <section className="card">
            <h2>Change your bank account</h2>
            <p>
              Merchant support can help you change the bank account where you receive payments. I
              can prepare a support request for you.
            </p>
            {!turn.action && (
              <button type="button" className="primary" onClick={ask}>
                Ask support
              </button>
            )}
          </section>
        )}
        {turn.intent === 'other' && (
          <section className="card">
            <p>
              I can check a short payment, prepare a customer offer, or put you in touch with
              support for a bank account change. Which would you like help with?
            </p>
          </section>
        )}
        {turn.action === 'confirm' && (
          <section className="card confirmation">
            <h2>{campaign ? 'Send this offer?' : 'Create a support request?'}</h2>
            <p>
              {campaign
                ? 'Simulate sending the offer above to ' +
                  audience.length +
                  ' customers at an estimated cost of ' +
                  offerCost +
                  '.'
                : payment
                  ? 'Share the payment breakdown and missing amount with simulated merchant support.'
                  : 'Ask simulated merchant support to help change your bank account.'}
            </p>
            <div className="actions">
              <button type="button" className="primary" onClick={approve}>
                {campaign ? 'Confirm simulated send' : 'Confirm support request'}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => update({ action: undefined })}
              >
                Cancel
              </button>
            </div>
          </section>
        )}
        {turn.approvedAt && campaign && delivery && (
          <section className="card outcome">
            <h2>Simulated delivery checked</h2>
            <p role="status">
              <strong>
                {delivery.delivered} delivered, {delivery.failed} failed
              </strong>
            </p>
          </section>
        )}
        {turn.approvedAt && !campaign && (
          <section className="card outcome">
            <h2>
              {turn.action === 'verified' ? 'Missing credit verified' : 'Support request created'}
            </h2>
            <p role="status">
              {turn.action === 'verified'
                ? money(missing) + ' arrived in a fresh sample bank record. The issue is closed.'
                : 'Pending with support.'}
            </p>
            {payment && turn.action === 'pending' && (
              <>
                <p className="fine">Follow-up scheduled for tomorrow in the demo.</p>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    if (readFollowup(turn)) update({ action: 'verified' });
                  }}
                >
                  Run simulated follow-up
                </button>
              </>
            )}
            <details>
              <summary>
                View details <span>· Ticket reference</span>
              </summary>
              <p>
                Simulated ticket <strong>{reference}</strong>
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
  const { chats, activeId, turns, draft, setTurns, setDraft, newChat, selectChat } = useChats();
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
  const focusComposer = () => window.requestAnimationFrame(() => input.current?.focus());
  const voice = useDictation(draft, setDraft, focusComposer);
  const working = turns.some(
    (turn) => turn.intent === 'payment' && !turn.replyText && now - turn.started < stages[3].at,
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
    const detected = detectIntent(question);
    const contextual =
      previousTurn &&
      previousTurn.intent !== 'other' &&
      (detected === 'other' || followup(previousTurn.intent).options.includes(question));
    const intent = contextual ? previousTurn.intent : detected;
    const replyText = contextual ? answerFollowup(intent, question) : undefined;
    setTurns((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        question,
        started,
        intent,
        replyText,
        offer: initialOffer,
      },
    ]);
    setDraft('');
    voice.reset();
    announce('Question sent.');
    focusComposer();
  }

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendQuestion(draft);
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
    announce('Demo reset.');
    focusComposer();
  }

  return (
    <div className="app-shell">
      <aside
        id="chat-history"
        className={sidebarOpen ? 'history-panel open' : 'history-panel'}
        aria-label="Chat history"
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setSidebarOpen(false);
            document.getElementById('history-toggle')?.focus();
          }
        }}
      >
        <div className="history-heading">
          <strong>Chat history</strong>
          <button
            type="button"
            className="secondary close-history"
            onClick={() => {
              setSidebarOpen(false);
              document.getElementById('history-toggle')?.focus();
            }}
          >
            Close
          </button>
        </div>
        <button type="button" className="primary new-chat" onClick={() => navigateChat()}>
          + New chat
        </button>
        <nav aria-label="Saved conversations">
          {chats.map((item) => (
            <button
              type="button"
              key={item.id}
              aria-current={item.id === activeId ? 'page' : undefined}
              onClick={() => navigateChat(item.id)}
              title={item.turns[0]?.question ?? 'New chat'}
            >
              <span>{item.turns[0]?.question ?? 'New chat'}</span>
              <small>
                {item.turns.length
                  ? item.turns.length + (item.turns.length === 1 ? ' message' : ' messages')
                  : 'Start a conversation'}
              </small>
            </button>
          ))}
        </nav>
        <p className="history-note">Chats are saved in this browser.</p>
        <button
          type="button"
          className="secondary theme-toggle"
          aria-pressed={theme === 'dark'}
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
        >
          {theme === 'light' ? 'Dark theme' : 'Light theme'}
        </button>
      </aside>
      {sidebarOpen && (
        <button
          type="button"
          className="history-backdrop"
          aria-label="Close chat history"
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
              <span className="sr-only">Chat history</span>
            </button>
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
                BizMate
              </span>
            </div>
            <div className="header-actions">
              <span className="merchant">
                <span className="merchant-logo" role="img" aria-label="Sharma General Store avatar">
                  SG
                </span>
                <span className="merchant-name">Sharma General Store</span>
              </span>
              <button
                className="replay"
                type="button"
                onClick={replay}
                aria-label="Replay demo"
                title="Replay demo"
              >
                <Icon name="replay" size={17} />
                <span>Replay demo</span>
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
                  <Icon name="sparkle" size={35} />
                  <span>✦</span>
                </div>
                <h1>Hi! How can I help?</h1>
                <p>Ask about a payment, bring customers back, or get help with your account.</p>
                <div className="prompts">
                  {questions.map((question, index) => (
                    <button
                      key={question}
                      type="button"
                      disabled={!!voice.mode}
                      onClick={() => {
                        setDraft(question);
                        focusComposer();
                      }}
                    >
                      <span className="tile">
                        <Icon name={(['payment', 'campaign', 'bank'] as const)[index]} />
                      </span>
                      <span>{question}</span>
                      <Icon name="arrow" size={16} />
                    </button>
                  ))}
                </div>
              </section>
            ) : (
              turns.map((turn) => (
                <article className="turn" key={turn.id}>
                  <div className="user-bubble">{turn.question}</div>
                  <ChatReply
                    turn={turn}
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
              if (last.intent === 'payment' && !last.replyText && now - last.started < stages[3].at)
                return null;
              const prompt = followup(last.intent);
              return (
                <section className="chat-column followup" aria-label="Follow-up questions">
                  <h2>{prompt.question}</h2>
                  <div className="followup-options">
                    {prompt.options.map((option) => (
                      <button
                        type="button"
                        className="secondary"
                        key={option}
                        disabled={!!voice.mode}
                        onClick={() => sendQuestion(option)}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                  <p>Choose an option, or type your answer below.</p>
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
                    Listening…{voice.mode === 'simulation' && <small>Simulated dictation</small>}
                  </span>
                  <div className="wave" aria-hidden="true">
                    {reduced ? (
                      <StaticWaveform bars={27} height={27} barColor="#007da5" />
                    ) : voice.mode === 'simulation' ? (
                      <ScrollingWaveform height={27} barWidth={3} barGap={3} barColor="#007da5" />
                    ) : (
                      <MicrophoneWaveform
                        active
                        height={27}
                        barWidth={3}
                        barGap={3}
                        barColor="#007da5"
                      />
                    )}
                  </div>
                  <button type="button" className="secondary" onClick={() => voice.end(true)}>
                    Cancel
                  </button>
                  <button type="button" className="primary" onClick={() => voice.end()}>
                    Done
                  </button>
                </div>
              )}
              <label className="sr-only" htmlFor="question">
                Type a question
              </label>
              <textarea
                id="question"
                ref={input}
                rows={2}
                maxLength={2000}
                placeholder="Type a question…"
                value={draft}
                readOnly={!!voice.mode}
                onChange={(event) => setDraft(event.target.value)}
              />
              <div className="composer-actions">
                <button
                  type="button"
                  className="secondary speak"
                  disabled={!!voice.mode}
                  onClick={() => voice.start(false)}
                >
                  <Icon name="mic" size={16} /> Speak
                </button>
                <button
                  type="button"
                  className="simulate"
                  disabled={!!voice.mode}
                  onClick={() => voice.start(true)}
                >
                  Simulate dictation
                </button>
                <button
                  type="submit"
                  className="primary send"
                  disabled={!draft.trim() || !!voice.mode}
                >
                  Send <Icon name="send" size={16} />
                </button>
              </div>
            </form>
            <div className="notice" role="status">
              {voice.notice}
            </div>
            <p className="demo-note">
              <span /> Demo mode · Sample data and simulated actions
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
