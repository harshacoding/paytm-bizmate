import { useEffect, useState } from 'react';
import type { SetStateAction } from 'react';
import { loadTurns } from './demo';
import type { Turn } from './demo';

type Chat = { id: string; turns: Turn[]; draft: string };
type History = { active: string; chats: Chat[] };
const key = 'bizmate-chats-v1';
const emptyChat = (): Chat => ({ id: crypto.randomUUID(), turns: [], draft: '' });

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
      return saved;
  } catch {
    /* Start a new history if browser storage is unavailable. */
  }
  const chat = { ...emptyChat(), turns: loadTurns() };
  return { active: chat.id, chats: [chat] };
}

export function useChats() {
  const [history, setHistory] = useState(loadHistory);
  const active = history.chats.find((chat) => chat.id === history.active)!;
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
      return { active: chat.id, chats: blank ? previous.chats : [chat, ...previous.chats] };
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
    selectChat: (id: string) => setHistory((previous) => ({ ...previous, active: id })),
  };
}
