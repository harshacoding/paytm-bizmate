import { useEffect, useState } from 'react';
import type { SetStateAction } from 'react';
import { loadTurns } from './demo';
import type { Turn } from './demo';
import { responseDuration, replyDelay, followupDelay } from './components/ResponseActivity';

type Chat = {
  id: string;
  turns: Turn[];
  draft: string;
  title?: string;
  unread?: number;
  lastReadAt?: number;
};
type History = { active: string; chats: Chat[] };
const key = 'bizmate-chats-v1';
const emptyChat = (): Chat => ({ id: crypto.randomUUID(), turns: [], draft: '' });

function responseTimes(chat: Chat) {
  return chat.turns.flatMap((turn) => {
    const primary = turn.started + responseDuration(turn);
    const times = [primary];
    if (['payment', 'campaign', 'bank', 'other'].includes(turn.intent))
      times.push(primary + followupDelay);
    if (turn.reportRequestedAt) times.push(turn.reportRequestedAt + replyDelay);
    if (turn.counterQuery) times.push(turn.counterQuery.checkedAt + replyDelay);
    if (turn.refundQuery) times.push(turn.refundQuery.checkedAt + replyDelay);
    return [...new Set(times)];
  });
}

function refreshUnread(history: History): History {
  const now = Date.now();
  return {
    ...history,
    chats: history.chats.map((chat) => {
      const times = responseTimes(chat);
      const lastReadAt =
        chat.id === history.active
          ? now
          : (chat.lastReadAt ?? (chat.unread ? Math.max(...times) - 1 : now));
      return {
        ...chat,
        lastReadAt,
        unread: times.filter((time) => time > lastReadAt && time <= now).length,
      };
    }),
  };
}

function sampleUpdate(): Chat {
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  return {
    id: 'sample-sales-update',
    title: 'Sales report update · Sample',
    unread: 1,
    draft: '',
    turns: [
      {
        id: 'sample-sales-ready',
        question: 'Review my sales report.',
        intent: 'sales',
        started: Date.now() - 100000,
        offer: '',
        salesMode: 'today',
        salesPeriod: { start: today, end: today },
        reportRequestedAt: Date.now() - 10000,
      },
    ],
  };
}

function loadHistory(): History {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? 'null');
    if (
      saved &&
      Array.isArray(saved.chats) &&
      saved.chats.length &&
      saved.chats.every(
        (chat: Chat) =>
          typeof chat.id === 'string' &&
          Array.isArray(chat.turns) &&
          typeof chat.draft === 'string',
      ) &&
      saved.chats.some((chat: Chat) => chat.id === saved.active)
    )
      return refreshUnread({
        ...saved,
        chats: saved.chats.some((chat: Chat) => chat.id === 'sample-sales-update')
          ? saved.chats
          : [...saved.chats, sampleUpdate()],
      });
  } catch {
    /* Start a new history if browser storage is unavailable. */
  }
  const chat = { ...emptyChat(), turns: loadTurns() };
  return refreshUnread({ active: chat.id, chats: [chat, sampleUpdate()] });
}

export function useChats() {
  const [history, setHistory] = useState(loadHistory);
  const active = history.chats.find((chat) => chat.id === history.active)!;
  useEffect(() => {
    const updated = refreshUnread(history);
    if (history.chats.some((chat, index) => chat.unread !== updated.chats[index].unread)) {
      setHistory(updated);
      return;
    }
    const now = Date.now();
    const next = Math.min(...history.chats.flatMap(responseTimes).filter((time) => time > now));
    if (!Number.isFinite(next)) return;
    const timer = window.setTimeout(() => setHistory(refreshUnread), next - now + 1);
    return () => window.clearTimeout(timer);
  }, [history]);
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(history));
    } catch {
      /* Keep chats in memory. */
    }
  }, [history]);

  function setTurns(action: SetStateAction<Turn[]>) {
    setHistory((previous) => ({
      ...previous,
      chats: previous.chats.map((chat) =>
        chat.id === previous.active
          ? {
              ...chat,
              lastReadAt: Date.now(),
              unread: 0,
              turns: typeof action === 'function' ? action(chat.turns) : action,
            }
          : chat,
      ),
    }));
  }
  function setDraft(draft: string) {
    setHistory((previous) => ({
      ...previous,
      chats: previous.chats.map((chat) =>
        chat.id === previous.active ? { ...chat, draft } : chat,
      ),
    }));
  }
  function newChat() {
    setHistory((previous) => {
      const blank = previous.chats.find((chat) => !chat.turns.length && !chat.draft);
      const chat = blank ?? emptyChat();
      return {
        active: chat.id,
        chats: (blank ? previous.chats : [chat, ...previous.chats]).map((item) =>
          item.id === previous.active || item.id === chat.id
            ? { ...item, lastReadAt: Date.now(), unread: 0 }
            : item,
        ),
      };
    });
  }
  return {
    chats: history.chats,
    activeId: active.id,
    turns: active.turns,
    draft: active.draft,
    setTurns,
    setDraft,
    newChat,
    selectChat: (id: string) =>
      setHistory((previous) => ({
        ...previous,
        active: id,
        chats: previous.chats.map((chat) =>
          chat.id === id || chat.id === previous.active
            ? { ...chat, unread: 0, lastReadAt: Date.now() }
            : chat,
        ),
      })),
  };
}
