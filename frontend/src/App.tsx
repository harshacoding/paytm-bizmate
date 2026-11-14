import { useEffect, useState, type FormEvent } from 'react';
import { api } from './api/client';
import type { DemoPreview, Session, Task } from './api/types';
import { DemoCards } from './components/DemoCards';
import { TaskTimeline } from './components/TaskTimeline';

const prompts = [
  'Why is my settlement short?',
  'Prepare an offer for inactive customers',
  'Change my registered bank account',
];

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [preview, setPreview] = useState<DemoPreview | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError('');
    Promise.all([api.health(), api.session(), api.tasks(), api.preview()])
      .then(([, s, t, p]) => {
        if (current) {
          setSession(s);
          setTasks(t);
          setPreview(p);
          setSelected((previous) =>
            t.some((task) => task.task_id === previous) ? previous : (t[0]?.task_id ?? null),
          );
        }
      })
      .catch((e) => {
        if (current) setError(e instanceof Error ? e.message : 'Unable to connect');
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [reload]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || sending) return;
    setSending(true);
    setError('');
    try {
      const task = await api.createTask(message);
      setTasks((previous) => [task, ...previous]);
      setSelected(task.task_id);
      setMessage('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save your request');
    } finally {
      setSending(false);
    }
  }

  const active = tasks.find((task) => task.task_id === selected);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="BizMate home">
          <span className="brand-mark">
            b<span>·</span>
          </span>
          <span>
            paytm <strong>BizMate</strong>
          </span>
        </a>
        <div className="workspace-label">MERCHANT WORKSPACE</div>
        <div className="nav-active">
          <span>▦</span> My workspace <span className="nav-dot" />
        </div>
        <div className="task-list-heading">
          <span>YOUR TASKS</span>
          <button
            onClick={() => setReload((n) => n + 1)}
            aria-label="Refresh tasks"
            disabled={loading}
          >
            ↻
          </button>
        </div>
        <nav aria-label="Your tasks" className="task-list">
          {tasks.map((task) => (
            <button
              key={task.task_id}
              className={selected === task.task_id ? 'task-link selected' : 'task-link'}
              aria-pressed={selected === task.task_id}
              onClick={() => setSelected(task.task_id)}
            >
              <span>{task.goal}</span>
              <small>{task.status.replaceAll('_', ' ').toLowerCase()}</small>
            </button>
          ))}
          {!loading && !tasks.length && (
            <p className="sidebar-empty">Your requests will appear here.</p>
          )}
        </nav>
        <div className="sidebar-bottom">
          <span className="avatar">SG</span>
          <div>
            <strong>{session?.merchant.display_name ?? 'Demo merchant'}</strong>
            <span>Synthetic local session</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>Your AI teammate for business</span>
          <span className="demo-pill">
            <i /> Local prototype
          </span>
        </header>
        <div className="content">
          <div className="welcome">
            <span className="eyebrow">A LITTLE LESS BUSYWORK</span>
            <h1>
              What’s on your mind
              <br />
              <span>for your business?</span>
            </h1>
            <p>Start with a request. Keep every next step in sight.</p>
          </div>
          <div className="notice">
            <span>ⓘ</span>
            <p>
              <strong>Development scaffold</strong> · Synthetic data, temporary memory storage.
              Requests can be saved; investigations, approvals and sends are still being built.
            </p>
          </div>
          {loading && (
            <p role="status" className="loading">
              Connecting to your workspace…
            </p>
          )}
          {error && (
            <div className="error" role="alert">
              <strong>Could not complete the request.</strong>
              <p>{error}</p>
              <button className="text-button" onClick={() => setReload((n) => n + 1)}>
                Retry connection
              </button>
              <p className="fineprint">For local setup, start both services with npm run dev.</p>
            </div>
          )}
          <section className="card composer">
            <form onSubmit={submit}>
              <label htmlFor="request">Tell BizMate what you need</label>
              <textarea
                id="request"
                placeholder="For example, why did I receive less than yesterday’s sales?"
                value={message}
                maxLength={4000}
                rows={2}
                onChange={(event) => setMessage(event.target.value)}
              />
              <div className="composer-bottom">
                <span>No live actions · demo intake only</span>
                <button
                  className="button primary"
                  type="submit"
                  disabled={loading || !session || !message.trim() || sending}
                >
                  {sending ? 'Saving…' : 'Start a task'} <span aria-hidden="true">↗</span>
                </button>
              </div>
            </form>
          </section>
          <div className="suggestions" aria-label="Example requests">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => {
                  setMessage(prompt);
                  document.getElementById('request')?.focus();
                }}
              >
                {prompt}
                <span aria-hidden="true">↗</span>
              </button>
            ))}
          </div>
          {active && <TaskTimeline task={active} />}
          {preview && <DemoCards preview={preview} />}
          <footer className="page-footer">
            Built for the Paytm Build for India AI Hackathon · Prototype workspace
          </footer>
        </div>
      </main>
    </div>
  );
}
