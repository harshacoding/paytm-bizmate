import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import DemoApp, { Icon } from './DemoApp';
import { LanguageProvider, useLanguage } from './i18n';
import { useWorkspace } from './useWorkspace';
import { useSidebarWidth } from './useSidebarWidth';
import { useDictation } from './useDictation';
import { LanguagePicker } from './components/LanguagePicker';
import { TaskWorkspace, taskLabel } from './components/TaskWorkspace';
import { BarVisualizer } from './components/elevenlabs/bar-visualizer';
import { Waveform, StaticWaveform } from './components/elevenlabs/waveform';
import { workspaceText } from './workspaceText';
import type { LanguageCode } from './api/types';
import { useUnread } from './useUnread';

export default function App() {
  if (new URLSearchParams(window.location.search).get('demo') === '1') return <DemoApp />;
  return (
    <LanguageProvider>
      <ConnectedApp />
    </LanguageProvider>
  );
}

function ConnectedApp() {
  const { language, setLanguage } = useLanguage();
  const t = (text: string) => workspaceText(text, language);
  const workspace = useWorkspace(setLanguage);
  const { unread, headers } = useUnread(
    workspace.session?.merchant.merchant_id,
    workspace.activeId,
    workspace.messages,
    workspace.opening,
  );
  const conversations = [
    ...new Map(
      [...(headers ?? []), ...workspace.conversations].map((item) => [item.conversation_id, item]),
    ).values(),
  ];
  const sidebar = useSidebarWidth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tab, setTab] = useState<'chat' | 'tasks'>('chat');
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [collapsedMessage, setCollapsedMessage] = useState<string | null>(null);
  const [allTasks, setAllTasks] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const chat = useRef<HTMLElement>(null);
  const focus = () => window.requestAnimationFrame(() => input.current?.focus());
  const voice = useDictation(workspace.draft, workspace.setDraft, focus);
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('bizmate-theme') ?? 'light';
    } catch {
      return 'light';
    }
  });
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  );
  const currentChat = workspace.conversations.find(
    (item) => item.conversation_id === workspace.activeId,
  );
  const selectedSnapshot = workspace.tasks.find((task) => task.task_id === selectedTask);
  const ticket = [
    ...(selectedSnapshot?.receipts ??
      workspace.tasks
        .filter((task) => task.conversation_id === workspace.activeId)
        .flatMap((task) => task.receipts)),
  ]
    .reverse()
    .find((receipt) => receipt.action === 'create_support_ticket')?.external_reference;
  const canWrite = !!workspace.session?.merchant.scopes.includes('tasks:write');
  const contextLanguage: LanguageCode =
    [...workspace.messages]
      .reverse()
      .find((message) => message.role === 'assistant' && message.response_language)
      ?.response_language ?? language;
  const taskLanguage: LanguageCode =
    [...workspace.messages]
      .reverse()
      .find((message) => message.task_id === selectedTask && message.response_language)
      ?.response_language ?? contextLanguage;
  const scopedTasks = workspace.tasks.filter(
    (task) => allTasks || (!!workspace.activeId && task.conversation_id === workspace.activeId),
  );
  const pendingHere =
    workspace.pending?.conversationId === workspace.activeId ? workspace.pending : null;
  const latestTaskMessage = [...workspace.messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.task_id);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('bizmate-theme', theme);
    } catch {}
  }, [theme]);
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media?.matches ?? false);
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, []);
  useLayoutEffect(() => {
    if (!input.current) return;
    input.current.style.height = 'auto';
    input.current.style.height = `${Math.min(input.current.scrollHeight, 120)}px`;
  }, [workspace.draft, language]);
  useEffect(() => {
    setSelectedTask(null);
    setCollapsedMessage(null);
    setTab('chat');
    voice.reset();
    // A recording belongs to the conversation where it started.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace.activeId]);
  useEffect(() => {
    const panel = chat.current;
    if (panel && panel.dataset.follow !== 'false') panel.scrollTop = panel.scrollHeight;
  }, [workspace.messages.length, workspace.pending?.id]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && sidebarOpen) {
        setSidebarOpen(false);
        document.getElementById('history-toggle')?.focus();
      }
    };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [sidebarOpen]);

  if (workspace.loading)
    return (
      <div className="api-startup" role="status">
        <div className="hero-mark">
          <Icon name="store" />
        </div>
        <p>{t('Connecting to your workspace…')}</p>
      </div>
    );
  if (!workspace.session)
    return (
      <div className="api-startup">
        <div className="hero-mark">
          <Icon name="store" />
        </div>
        <h1>{t('Workspace unavailable')}</h1>
        <p role="alert">{workspace.error}</p>
        <button className="primary" onClick={() => void workspace.bootstrap()}>
          {t('Retry connection')}
        </button>
        <a href="?demo=1">{t('Sample walkthrough')}</a>
      </div>
    );

  const session = workspace.session;
  return (
    <div
      className="app-shell api-shell"
      style={{ '--sidebar-width': `${sidebar.width}px` } as CSSProperties}
      data-resizing={sidebar.resizing}
    >
      <aside
        id="chat-history"
        className={`history-panel ${sidebarOpen ? 'open' : ''}`}
        aria-label={t('Chat history')}
      >
        <div className="sidebar-brand">
          <img src="/brand/paytm.png" alt="Paytm" />
          <span className="sidebar-bizmate">
            <Icon name="store" size={17} />
            BizMate
          </span>
        </div>
        <div className="history-heading">
          <strong>{t('Chat history')}</strong>
          <button className="secondary close-history" onClick={() => setSidebarOpen(false)}>
            {t('Close')}
          </button>
        </div>
        <button
          className="primary new-chat"
          disabled={!canWrite || workspace.busy || !!voice.mode}
          onClick={() => {
            setSidebarOpen(false);
            void workspace.newConversation(language);
          }}
        >
          {t('+ New chat')}
        </button>
        <nav aria-label={t('Saved conversations')}>
          {[...conversations].reverse().map((conversation) => (
            <button
              key={conversation.conversation_id}
              title={conversation.title}
              aria-current={
                conversation.conversation_id === workspace.activeId ? 'page' : undefined
              }
              onClick={() => {
                workspace.select(conversation.conversation_id);
                setSidebarOpen(false);
              }}
            >
              <span className="history-row">
                <span className="history-title">{conversation.title}</span>
                {conversation.conversation_id !== workspace.activeId &&
                  !!unread[conversation.conversation_id] && (
                    <span
                      className="unread-badge"
                      aria-label={`${unread[conversation.conversation_id]} ${t('unread messages')}`}
                    >
                      {unread[conversation.conversation_id]}
                    </span>
                  )}
              </span>
            </button>
          ))}
        </nav>
        <p className="history-note">{t('Saved on the server')}</p>
        <LanguagePicker
          disabled={workspace.busy || !!voice.mode || (!canWrite && !!workspace.activeId)}
          onSelect={voice.reset}
          onLanguageChange={(value) => void workspace.changeLanguage(value)}
        />
        <button
          className="secondary theme-toggle"
          aria-pressed={theme === 'dark'}
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {t(theme === 'dark' ? 'Light theme' : 'Dark theme')}
        </button>
        <a className="api-demo-link" href="?demo=1">
          {t('Sample walkthrough')} ↗
        </a>
        <div
          className="sidebar-resizer"
          role="separator"
          aria-label={t('Resize chat history')}
          aria-orientation="vertical"
          aria-valuemin={200}
          aria-valuemax={420}
          aria-valuenow={Math.round(sidebar.width)}
          tabIndex={0}
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
          onKeyDown={(event) => {
            if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
              event.preventDefault();
              sidebar.resize(
                event.key === 'Home'
                  ? 200
                  : event.key === 'End'
                    ? 420
                    : sidebar.width + (event.key === 'ArrowLeft' ? -16 : 16),
              );
            }
          }}
        />
      </aside>
      {sidebarOpen && (
        <button
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
              className="secondary history-toggle"
              aria-label={t('Chat history')}
              aria-controls="chat-history"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              ☰
            </button>
            <div className="chat-title" aria-live="polite">
              <span className="chat-title-text">{currentChat?.title ?? t('New chat')}</span>
              {ticket && <span className="chat-ticket">{ticket}</span>}
            </div>
            <span className="merchant">
              <span className="merchant-logo">
                <Icon name="store" size={20} />
              </span>
              <span className="merchant-name">{workspace.session.merchant.display_name}</span>
            </span>
          </div>
        </header>
        <main
          ref={chat}
          className="chat"
          data-conversation={workspace.activeId ?? ''}
          onScroll={(event) => {
            const panel = event.currentTarget;
            panel.dataset.follow = String(
              panel.scrollHeight - panel.clientHeight - panel.scrollTop < 72,
            );
          }}
        >
          <div className="chat-column api-column">
            <div className="api-tabs" aria-label={t('Conversation')}>
              <button
                aria-pressed={tab === 'chat'}
                onClick={() => {
                  setTab('chat');
                  setSelectedTask(null);
                }}
              >
                {t('Conversation')}
              </button>
              <button aria-pressed={tab === 'tasks'} onClick={() => setTab('tasks')}>
                {t('Your tasks')}
                <span>
                  {
                    workspace.tasks.filter(
                      (task) => !!workspace.activeId && task.conversation_id === workspace.activeId,
                    ).length
                  }
                </span>
              </button>
            </div>
            {workspace.error && (
              <div className="api-error" role="alert">
                <p>{workspace.error}</p>
                {workspace.activeId && (
                  <button
                    className="secondary"
                    onClick={() => void workspace.refreshChat(workspace.activeId!)}
                  >
                    {t('Refresh')}
                  </button>
                )}
              </div>
            )}
            {tab === 'tasks' ? (
              selectedTask ? (
                <TaskWorkspace
                  key={selectedTask}
                  id={selectedTask}
                  session={session}
                  language={taskLanguage}
                  onTask={workspace.updateTask}
                  onClose={() => {
                    setSelectedTask(null);
                    setTab('chat');
                  }}
                />
              ) : (
                <section className="api-task-list">
                  <div className="api-section-heading">
                    <h2>{t('Your tasks')}</h2>
                    <button
                      className="secondary"
                      aria-pressed={allTasks}
                      onClick={() => setAllTasks(!allTasks)}
                    >
                      {t(allTasks ? 'Tasks in this chat' : 'All tasks')}
                    </button>
                  </div>
                  {scopedTasks.length ? (
                    scopedTasks.map((task) => (
                      <button
                        className="api-task-row"
                        key={task.task_id}
                        onClick={() => setSelectedTask(task.task_id)}
                      >
                        <span>
                          <strong>{task.goal}</strong>
                          <small>{task.next_action}</small>
                        </span>
                        <span className={`api-status status-${task.status.toLowerCase()}`}>
                          {taskLabel(task, contextLanguage)}
                        </span>
                        <span aria-hidden="true">↗</span>
                      </button>
                    ))
                  ) : (
                    <p>{t('No tasks yet')}</p>
                  )}
                </section>
              )
            ) : (
              <>
                {workspace.opening ? (
                  <p role="status">{t('Loading conversation…')}</p>
                ) : workspace.messages.length === 0 && !pendingHere ? (
                  <section className="welcome api-welcome">
                    <div className="hero-mark">
                      <Icon name="store" size={30} />
                    </div>
                    <h1>{t('Hi! How can I help?')}</h1>
                    <p>
                      {t(
                        'Ask about a payment, bring customers back, or get help with your account.',
                      )}
                    </p>
                    <div className="prompts">
                      {[
                        'Why is my payment short?',
                        'Did I receive ₹480?',
                        'Where is my ₹650 refund?',
                        'How much did I collect today?',
                        'Help me bring customers back.',
                      ].map((question) => (
                        <button
                          key={question}
                          disabled={!canWrite || !!voice.mode}
                          onClick={() => {
                            workspace.setDraft(t(question));
                            focus();
                          }}
                        >
                          <span className="tile">
                            <Icon name={question.includes('customers') ? 'campaign' : 'payment'} />
                          </span>
                          <span>{t(question)}</span>
                          <Icon name="arrow" size={16} />
                        </button>
                      ))}
                    </div>
                  </section>
                ) : (
                  workspace.messages.map((message) => (
                    <article
                      key={message.message_id}
                      className={`api-message ${message.role}`}
                      lang={
                        message.role === 'assistant'
                          ? (message.response_language ?? undefined)
                          : (message.detected_language ?? undefined)
                      }
                    >
                      {message.role === 'user' ? (
                        <div className="user-bubble">{message.content}</div>
                      ) : (
                        <div className="api-assistant">
                          <span className="reply-avatar" aria-hidden="true">
                            <Icon name="store" size={16} />
                          </span>
                          <div className="api-message-content">{message.content}</div>
                        </div>
                      )}
                      {message.message_id === latestTaskMessage?.message_id &&
                        message.message_id !== collapsedMessage &&
                        message.task_id && (
                          <TaskWorkspace
                            key={message.task_id}
                            id={message.task_id}
                            session={session}
                            language={message.response_language ?? contextLanguage}
                            onTask={workspace.updateTask}
                            onClose={() => setCollapsedMessage(message.message_id)}
                            embedded
                          />
                        )}
                      {message.task_id && (
                        <button
                          className="secondary"
                          onClick={() => {
                            setTab('tasks');
                            setSelectedTask(message.task_id);
                          }}
                        >
                          {t('Task details')}
                        </button>
                      )}
                    </article>
                  ))
                )}
                {pendingHere && (
                  <article className="api-message user">
                    <div className="user-bubble">{pendingHere.content}</div>
                    {pendingHere.failed ? (
                      <div className="api-error" role="status">
                        <p>{t('Message not confirmed')}</p>
                        <button
                          className="secondary"
                          disabled={workspace.busy}
                          onClick={() => void workspace.send(language, true)}
                        >
                          {t('Retry this exact message')}
                        </button>
                      </div>
                    ) : (
                      <div className="response-activity" role="status">
                        <BarVisualizer
                          aria-hidden="true"
                          className="thinking"
                          state={reduced ? undefined : 'thinking'}
                          barCount={5}
                          minHeight={30}
                          maxHeight={95}
                        />
                        <span>{t('Sending your message…')}</span>
                      </div>
                    )}
                  </article>
                )}
              </>
            )}
          </div>
        </main>
        <footer className="composer-region">
          <div className="chat-column">
            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                if (!voice.mode && !workspace.opening && canWrite) {
                  setTab('chat');
                  setSelectedTask(null);
                  void workspace.send(language);
                }
              }}
            >
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
                  <button className="secondary" type="button" onClick={() => void voice.end(true)}>
                    {t('Cancel')}
                  </button>
                  <button
                    className="primary"
                    type="button"
                    disabled={voice.mode !== 'mic'}
                    onClick={() => void voice.end()}
                  >
                    {t('Done')}
                  </button>
                </div>
              )}
              <div className="composer-input">
                <label htmlFor="api-question" className="sr-only">
                  {t('Type a question')}
                </label>
                <textarea
                  id="api-question"
                  ref={input}
                  rows={1}
                  maxLength={4000}
                  placeholder={t('Type a question…')}
                  value={workspace.draft}
                  disabled={!canWrite}
                  readOnly={!!voice.mode}
                  onChange={(event) => workspace.setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === 'Enter' &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <div className="composer-actions">
                  <button
                    className="secondary speak"
                    aria-label={t('Speak')}
                    title={t('Speak')}
                    type="button"
                    disabled={!canWrite || !!voice.mode || workspace.busy || workspace.opening}
                    onClick={() => void voice.start()}
                  >
                    <Icon name="mic" size={16} />
                  </button>
                  <button
                    className="primary send"
                    aria-label={t('Send')}
                    disabled={
                      !canWrite ||
                      !workspace.draft.trim() ||
                      !!voice.mode ||
                      workspace.busy ||
                      workspace.opening ||
                      !!workspace.pending
                    }
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
              {t('Synthetic data · Simulated actions')}
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
