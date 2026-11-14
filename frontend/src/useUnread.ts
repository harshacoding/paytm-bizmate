import { useEffect, useRef, useState } from 'react';
import { api } from './api/client';
import type { Conversation, ConversationMessage } from './api/types';

export function useUnread(
  merchantId: string | undefined,
  activeId: string | null,
  messages: ConversationMessage[],
  opening: boolean,
) {
  const [unread, setUnread] = useState<Record<string, number>>({});
  const seen = useRef<Record<string, number>>({});
  const active = useRef(activeId);
  active.current = activeId;
  const [headers, setHeaders] = useState<Conversation[] | null>(null);
  useEffect(() => {
    if (!merchantId) return;
    try {
      seen.current = JSON.parse(localStorage.getItem(`bizmate-read-${merchantId}`) ?? '{}');
    } catch {
      seen.current = {};
    }
    let cancelled = false;
    let inFlight = false;
    async function refresh() {
      if (document.hidden || inFlight) return;
      inFlight = true;
      try {
        const conversations = await api.conversations();
        if (cancelled) return;
        setHeaders(conversations);
        const counts = await Promise.all(
          conversations
            .filter((item) => item.conversation_id !== active.current)
            .map(async (item) => {
              try {
                const history = await api.messages(item.conversation_id);
                return [
                  item.conversation_id,
                  [
                    ...new Map(history.map((message) => [message.message_id, message])).values(),
                  ].filter(
                    (message) =>
                      message.role === 'assistant' &&
                      message.sequence > (seen.current[item.conversation_id] ?? 0),
                  ).length,
                ] as const;
              } catch {
                return [item.conversation_id, 0] as const;
              }
            }),
        );
        if (!cancelled)
          setUnread(Object.fromEntries(counts.filter(([id]) => id !== active.current)));
      } catch {
        /* Foreground actions surface connection errors; background checks leave the screen usable. */
      } finally {
        inFlight = false;
      }
    }
    void refresh();
    const interval = window.setInterval(() => void refresh(), 10000);
    const visible = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener('visibilitychange', visible);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', visible);
    };
  }, [merchantId]);
  useEffect(() => {
    if (
      !merchantId ||
      !activeId ||
      opening ||
      messages.some((message) => message.conversation_id !== activeId)
    )
      return;
    seen.current[activeId] = Math.max(
      seen.current[activeId] ?? 0,
      ...messages.map((message) => message.sequence),
    );
    setUnread((previous) => (previous[activeId] ? { ...previous, [activeId]: 0 } : previous));
    try {
      localStorage.setItem(`bizmate-read-${merchantId}`, JSON.stringify(seen.current));
    } catch {}
  }, [merchantId, activeId, messages, opening]);
  return { unread, headers };
}
