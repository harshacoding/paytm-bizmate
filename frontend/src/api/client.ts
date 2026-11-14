import type { DemoPreview, Health, Session, Task } from './types';

export const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.message ??
        (typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`),
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>('/health'),
  session: () => request<Session>('/api/v1/session'),
  tasks: () => request<Task[]>('/api/v1/tasks'),
  preview: () => request<DemoPreview>('/api/v1/demo/preview'),
  createTask: (message: string) =>
    request<Task>('/api/v1/tasks', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
};
