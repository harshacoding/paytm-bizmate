import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api/client';
import type { Conversation, ConversationMessage, LanguageCode, Session, Task } from './api/types';

type PendingTurn = { conversationId: string; content: string; id: string; failed: boolean };
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Something went wrong.';
export function orderedMessages(messages: ConversationMessage[]) {
  return [...new Map(messages.map((message) => [message.message_id, message])).values()].sort(
    (a, b) => a.sequence - b.sequence,
  );
}

export function useWorkspace(setLanguage: (language: LanguageCode) => void) {
  const [session, setSession] = useState<Session | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const active = useRef(activeId);
  active.current = activeId;
  const loadSequence = useRef(0);
  const lock = useRef(false);
  const mounted = useRef(true);
  const sessionRef = useRef<Session | null>(null);
  const pendingKey = (id: string) => `bizmate-pending-${id}`;
  const rememberPending = (value: PendingTurn | null) => {
    setPending(value);
    try {
      const merchant = sessionRef.current?.merchant.merchant_id;
      if (merchant) {
        if (value) sessionStorage.setItem(pendingKey(merchant), JSON.stringify(value));
        else sessionStorage.removeItem(pendingKey(merchant));
      }
    } catch {
      /* Storage is optional; API remains authoritative. */
    }
  };

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [identity, chats, savedTasks] = await Promise.all([
        api.session(),
        api.conversations(),
        api.tasks(),
      ]);
      if (!mounted.current) return;
      sessionRef.current = identity;
      setSession(identity);
      setConversations(chats);
      setTasks(savedTasks);
      let remembered: string | null = null;
      try {
        remembered = localStorage.getItem(`bizmate-active-${identity.merchant.merchant_id}`);
        const saved = JSON.parse(
          sessionStorage.getItem(pendingKey(identity.merchant.merchant_id)) ?? 'null',
        );
        if (
          saved &&
          chats.some((chat) => chat.conversation_id === saved.conversationId) &&
          typeof saved.content === 'string' &&
          typeof saved.id === 'string'
        )
          setPending({ ...saved, failed: true });
      } catch {
        /* No saved selection. */
      }
      const chosen = chats.find((chat) => chat.conversation_id === remembered) ?? chats.at(-1);
      setActiveId(chosen?.conversation_id ?? null);
      setLanguage(chosen?.preferred_language ?? identity.merchant.preferred_language);
    } catch (failure) {
      if (mounted.current) setError(errorText(failure));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [setLanguage]);

  useEffect(() => {
    mounted.current = true;
    void bootstrap();
    return () => {
      mounted.current = false;
      loadSequence.current++;
    };
  }, [bootstrap]);

  const refreshChat = useCallback(
    async (id: string) => {
      const sequence = ++loadSequence.current;
      setOpening(true);
      setError('');
      try {
        const [conversation, history, savedTasks] = await Promise.all([
          api.conversation(id),
          api.messages(id),
          api.tasks(),
        ]);
        if (!mounted.current || active.current !== id || sequence !== loadSequence.current) return;
        setMessages(orderedMessages(history));
        setTasks(savedTasks);
        setConversations((previous) =>
          previous.map((chat) => (chat.conversation_id === id ? conversation : chat)),
        );
        setLanguage(conversation.preferred_language);
      } catch (failure) {
        if (mounted.current && sequence === loadSequence.current) setError(errorText(failure));
      } finally {
        if (mounted.current && sequence === loadSequence.current) setOpening(false);
      }
    },
    [setLanguage],
  );

  useEffect(() => {
    setMessages([]);
    if (activeId) {
      try {
        localStorage.setItem(
          `bizmate-active-${sessionRef.current?.merchant.merchant_id}`,
          activeId,
        );
      } catch {}
      void refreshChat(activeId);
    } else {
      loadSequence.current++;
      setOpening(false);
    }
  }, [activeId, refreshChat]);

  async function newConversation(language: LanguageCode) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const conversation = await api.createConversation(language);
      if (!mounted.current) return;
      setConversations((previous) => [...previous, conversation]);
      setActiveId(conversation.conversation_id);
      return conversation;
    } catch (failure) {
      if (mounted.current) setError(errorText(failure));
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function send(language: LanguageCode, retry = false) {
    if (lock.current || (pending && !retry)) return;
    const content = retry ? pending?.content : (drafts[activeId ?? 'new'] ?? '');
    if (!content?.trim()) return;
    lock.current = true;
    setBusy(true);
    setError('');
    let turn = retry ? pending : null;
    try {
      let id = retry ? pending!.conversationId : active.current;
      if (!id) {
        const conversation = await api.createConversation(language, content.trim().slice(0, 80));
        id = conversation.conversation_id;
        setConversations((previous) => [...previous, conversation]);
        setActiveId(id);
        active.current = id;
      }
      turn = turn ?? {
        conversationId: id,
        content,
        id: `ui-${crypto.randomUUID()}`,
        failed: false,
      };
      rememberPending({ ...turn, failed: false });
      setDrafts((previous) => ({ ...previous, [id]: '', new: '' }));
      // Preference is persisted separately; do not misrepresent it as detected message language.
      const reply = await api.sendMessage(id, turn.content, turn.id);
      if (!mounted.current) return;
      if (active.current === id) {
        loadSequence.current++;
        setOpening(false);
        setMessages((previous) =>
          orderedMessages([...previous, reply.user_message, reply.assistant_message]),
        );
      }
      rememberPending(null);
      const chats = await api.conversations();
      if (mounted.current) setConversations(chats);
    } catch (failure) {
      if (mounted.current) {
        if (turn) rememberPending({ ...turn, failed: true });
        setError(errorText(failure));
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function changeLanguage(language: LanguageCode) {
    const id = active.current;
    if (!id) {
      const conversation = await newConversation(language);
      if (conversation) setLanguage(conversation.preferred_language);
      return;
    }
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const conversation = await api.setLanguage(id, language);
      if (!mounted.current) return;
      setConversations((previous) =>
        previous.map((chat) => (chat.conversation_id === id ? conversation : chat)),
      );
      if (active.current === id) setLanguage(conversation.preferred_language);
    } catch (failure) {
      if (mounted.current) setError(errorText(failure));
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  function updateTask(task: Task) {
    setTasks((previous) => {
      const current = previous.find((item) => item.task_id === task.task_id);
      if (current && current.revision > task.revision) return previous;
      return [task, ...previous.filter((item) => item.task_id !== task.task_id)];
    });
  }

  return {
    session,
    conversations,
    activeId,
    messages,
    tasks,
    loading,
    opening,
    error,
    busy,
    pending,
    draft: drafts[activeId ?? 'new'] ?? '',
    setDraft: (value: string) =>
      setDrafts((previous) => ({ ...previous, [active.current ?? 'new']: value })),
    select: (id: string) => {
      setActiveId(id);
      active.current = id;
    },
    newConversation,
    send,
    changeLanguage,
    refreshChat,
    bootstrap,
    updateTask,
    setError,
  };
}
