import type {
  ActionInputs,
  Approval,
  Conversation,
  ConversationMessage,
  ConversationTurn,
  CustomerSegment,
  DemoPreview,
  Health,
  LanguageCode,
  Receipt,
  Session,
  SettlementProof,
  Task,
  TaskEvent,
  Verification,
} from './types';

export const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public taskReference: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      0,
      'NETWORK_ERROR',
      'Connection interrupted. Refresh saved records before trying again.',
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      response.status,
      body?.code ?? 'HTTP_ERROR',
      body?.message ?? `Request failed (${response.status})`,
      body?.task_reference ?? null,
    );
  if (body === null)
    throw new ApiError(
      response.status,
      'INVALID_RESPONSE',
      'The server returned an unreadable response.',
    );
  return body as T;
}

const pathId = encodeURIComponent;
const json = (body: unknown, method = 'POST') => ({ method, body: JSON.stringify(body) });
const taskPath = (id: string) => `/api/v1/tasks/${pathId(id)}`;
const chatPath = (id: string) => `/api/v1/conversations/${pathId(id)}`;

export const api = {
  health: () => request<Health>('/health'),
  session: () => request<Session>('/api/v1/session'),
  conversations: () => request<Conversation[]>('/api/v1/conversations'),
  createConversation: (preferred_language: LanguageCode, title = 'New conversation') =>
    request<Conversation>('/api/v1/conversations', json({ title, preferred_language })),
  conversation: (id: string) => request<Conversation>(chatPath(id)),
  messages: (id: string) => request<ConversationMessage[]>(`${chatPath(id)}/messages`),
  setLanguage: (id: string, preferred_language: LanguageCode) =>
    request<Conversation>(chatPath(id), json({ preferred_language }, 'PATCH')),
  sendMessage: (id: string, content: string, client_message_id: string) =>
    request<ConversationTurn>(`${chatPath(id)}/messages`, json({ content, client_message_id })),
  tasks: (conversationId?: string) =>
    request<Task[]>(
      `/api/v1/tasks${conversationId ? `?conversation_id=${pathId(conversationId)}` : ''}`,
    ),
  task: (id: string) => request<Task>(taskPath(id)),
  events: (id: string) => request<TaskEvent[]>(`${taskPath(id)}/events`),
  preview: () => request<DemoPreview>('/api/v1/demo/preview'),
  createTask: (message: string, conversation_id?: string) =>
    request<Task>(
      '/api/v1/tasks',
      json({ message, ...(conversation_id ? { conversation_id } : {}) }),
    ),
  clarify: (id: string, message: string) =>
    request<Task>(`${taskPath(id)}/messages`, json({ message })),
  requestApproval: (id: string, action: string, inputs: ActionInputs) =>
    request<Approval>(`${taskPath(id)}/approvals`, json({ action, inputs })),
  decide: (id: string, approval: Approval, decision: 'approve' | 'cancel') =>
    request<Approval>(
      `${taskPath(id)}/approvals/${pathId(approval.approval_id)}`,
      json({ decision, input_hash: approval.input_hash }),
    ),
  execute: (id: string, approval: Approval) =>
    request<Receipt>(
      `${taskPath(id)}/approvals/${pathId(approval.approval_id)}/execute`,
      json({ inputs: approval.approved_inputs }),
    ),
  verify: (id: string, receiptId: string) =>
    request<Verification>(`${taskPath(id)}/receipts/${pathId(receiptId)}/verify`, {
      method: 'POST',
    }),
  segment: (inactivity_days = 30) =>
    request<CustomerSegment>('/api/v1/campaigns/segment', json({ inactivity_days })),
  reconcile: () => request<SettlementProof>('/api/v1/settlements/reconcile', json({})),
};
