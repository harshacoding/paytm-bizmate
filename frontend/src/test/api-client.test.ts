import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, ApiError, request } from '../api/client';
import type { Approval } from '../api/types';

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi
    .fn()
    .mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
const sentBody = () => JSON.parse(fetchMock.mock.calls.at(-1)![1].body);

it('sends original message content with a stable retry id and no forced language/identity fields', async () => {
  await api.sendMessage('chat/one', '  తెలుగు ప్రశ్న  ', 'ui-retry-one');
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/conversations/chat%2Fone/messages',
    expect.anything(),
  );
  expect(sentBody()).toEqual({ content: '  తెలుగు ప్రశ్న  ', client_message_id: 'ui-retry-one' });
});
it('persists only the fallback preference through PATCH', async () => {
  await api.setLanguage('chat-one', 'te');
  expect(fetchMock.mock.calls[0][1].method).toBe('PATCH');
  expect(sentBody()).toEqual({ preferred_language: 'te' });
});
it('uses the exact server hash and approved inputs for decisions and execution', async () => {
  const approval = {
    task_id: 'task-one',
    merchant_id: 'merchant_demo',
    action: 'create_support_ticket',
    decision: 'approved',
    approver: 'demo_actor_merchant_demo',
    decided_at: '2026-11-14T07:32:53Z',
    approval_id: 'approval-one',
    input_hash: 'c'.repeat(64),
    approved_inputs: { task_id: 'task-one', summary: '  Preserve this text  ' },
  } satisfies Approval;
  await api.decide('task-one', approval, 'approve');
  expect(sentBody()).toEqual({ decision: 'approve', input_hash: approval.input_hash });
  fetchMock.mockResolvedValueOnce(new Response('{}'));
  await api.execute('task-one', approval);
  expect(sentBody()).toEqual({ inputs: approval.approved_inputs });
});
it('verification is a bodyless POST and does not execute the action', async () => {
  await api.verify('task-one', 'receipt-one');
  expect(fetchMock).toHaveBeenCalledOnce();
  expect(fetchMock.mock.calls[0]).toEqual([
    '/api/v1/tasks/task-one/receipts/receipt-one/verify',
    { method: 'POST', headers: {} },
  ]);
});
it.each([403, 404, 409, 422, 503])('preserves structured errors for HTTP %s', async (status) => {
  fetchMock.mockResolvedValue(
    new Response(
      JSON.stringify({
        code: 'CONTRACT_ERROR',
        message: 'Saved error message',
        task_reference: 'task-one',
      }),
      { status },
    ),
  );
  await expect(request('/test')).rejects.toMatchObject({
    status,
    code: 'CONTRACT_ERROR',
    message: 'Saved error message',
    taskReference: 'task-one',
  });
});
it('handles non-JSON responses without exposing HTML or provider details', async () => {
  fetchMock.mockResolvedValue(new Response('<html>Provider stack</html>', { status: 500 }));
  await expect(request('/test')).rejects.toMatchObject({
    status: 500,
    message: 'Request failed (500)',
  });
});
it('does not automatically retry a timed-out mutation', async () => {
  fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
  await expect(api.createTask('Question')).rejects.toBeInstanceOf(ApiError);
  expect(fetchMock).toHaveBeenCalledOnce();
});
