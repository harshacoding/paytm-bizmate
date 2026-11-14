import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { api, ApiError } from '../api/client';
import type {
  Approval,
  Conversation,
  ConversationMessage,
  CustomerSegment,
  Receipt,
  Session,
  Task,
  Verification,
} from '../api/types';
import { task as scaffold, session as identity } from './fixtures';
import { TaskWorkspace } from '../components/TaskWorkspace';
import { paise } from '../api/format';
import { workspaceText } from '../workspaceText';
import ticketFixture from './contract-fixtures/ui-ticket-fixture.json';
import campaignFixture from './contract-fixtures/ui-campaign-fixture.json';

const date = '2026-11-14T07:32:53Z';
const session: Session = {
  ...identity,
  merchant: {
    ...identity.merchant,
    scopes: [
      'tasks:read',
      'tasks:write',
      'tasks:approve',
      'payments:read',
      'customers:read',
      'tickets:write',
      'campaigns:write',
    ],
  },
};
const conversation: Conversation = {
  conversation_id: 'chat-1',
  merchant_id: 'merchant_demo',
  title: 'Settlement questions',
  preferred_language: 'en',
  created_at: date,
  updated_at: date,
};
const other: Conversation = {
  ...conversation,
  conversation_id: 'chat-2',
  title: 'Second conversation',
};
const message = (
  id: string,
  content: string,
  role: 'user' | 'assistant',
  sequence: number,
): ConversationMessage => ({
  message_id: id,
  conversation_id: 'chat-1',
  merchant_id: 'merchant_demo',
  role,
  content,
  sequence,
  created_at: date,
  detected_language: null,
  response_language: role === 'assistant' ? 'en' : null,
  task_id: null,
  language: null,
});
const approval: Approval = {
  task_id: 'task-one',
  merchant_id: 'merchant_demo',
  approval_id: 'approval-one',
  action: 'create_support_ticket',
  approved_inputs: { task_id: 'task-one', summary: '  Investigate ₹166.80  ' },
  input_hash: 'a'.repeat(64),
  decision: 'pending',
  approver: null,
  decided_at: null,
};
const receipt: Receipt = {
  task_id: 'task-one',
  merchant_id: 'merchant_demo',
  receipt_id: 'receipt-one',
  action: 'create_support_ticket',
  external_reference: 'BM-16680',
  idempotency_key: 'execution-one',
  input_hash: approval.input_hash,
  created_at: date,
};
const verification: Verification = {
  task_id: 'task-one',
  merchant_id: 'merchant_demo',
  receipt_id: receipt.receipt_id,
  verification_id: 'verification-one',
  tool_name: 'get_ticket_status',
  verified: false,
  evidence_reference: 'ticket-source',
  verified_at: date,
};
let snapshot: Task;
let history: ConversationMessage[];
const onClose = vi.fn();

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState({}, '', '/');
  onClose.mockReset();
  snapshot = structuredClone({ ...scaffold, conversation_id: 'chat-1' });
  history = [];
  vi.spyOn(api, 'session').mockResolvedValue(session);
  vi.spyOn(api, 'conversations').mockResolvedValue([conversation, other]);
  vi.spyOn(api, 'conversation').mockImplementation(async (id) =>
    id === 'chat-2' ? other : conversation,
  );
  vi.spyOn(api, 'messages').mockImplementation(async () => structuredClone(history));
  vi.spyOn(api, 'tasks').mockImplementation(async () => [structuredClone(snapshot)]);
  vi.spyOn(api, 'task').mockImplementation(async () => structuredClone(snapshot));
  vi.spyOn(api, 'resume').mockImplementation(async () => structuredClone(snapshot));
  vi.spyOn(api, 'runDueSettlements').mockResolvedValue([]);
  vi.spyOn(api, 'resumeInvestigation').mockImplementation(async () => ({
    task: structuredClone(snapshot),
    state: {
      request: {
        client_request_id: 'ui-settlement',
        settlement_reference: 'settlement-001',
        message: 'Why is my settlement short?',
        conversation_id: 'chat-1',
      },
      phase: 'approval',
      proof: null,
      case_summary: null,
      approval_id: null,
      receipt_id: null,
      report_attempts: 1,
      follow_up_attempts: 0,
      claim_until: null,
    },
    resolution: null,
  }));
  vi.spyOn(api, 'events').mockImplementation(async () => structuredClone(snapshot.events));
  vi.spyOn(api, 'createConversation').mockResolvedValue({
    ...conversation,
    conversation_id: 'chat-new',
    title: 'New conversation',
  });
  vi.spyOn(api, 'setLanguage').mockImplementation(async (_id, language) => ({
    ...conversation,
    preferred_language: language,
  }));
  vi.spyOn(api, 'sendMessage').mockImplementation(async (id, content, clientId) => {
    const user = { ...message('user-one', content, 'user', 1), conversation_id: id };
    const assistant = {
      ...message('assistant-one', 'Saved server reply.', 'assistant', 2),
      conversation_id: id,
    };
    history = [user, assistant];
    return { client_message_id: clientId, user_message: user, assistant_message: assistant };
  });
  vi.spyOn(api, 'createTask').mockImplementation(async () => structuredClone(snapshot));
  vi.spyOn(api, 'clarify').mockImplementation(async (_id, content) => {
    snapshot.events.push({
      event_id: 'clarification',
      kind: 'merchant_message',
      message: content,
      occurred_at: date,
    });
    return structuredClone(snapshot);
  });
  vi.spyOn(api, 'requestApproval').mockImplementation(async (_id, action, inputs) => {
    const saved = { ...approval, action, approved_inputs: inputs };
    snapshot = { ...snapshot, status: 'AWAITING_APPROVAL', approvals: [saved] };
    return saved;
  });
  vi.spyOn(api, 'decide').mockImplementation(async (_id, saved, decision) => {
    const result: Approval = {
      ...saved,
      decision: decision === 'approve' ? 'approved' : 'cancelled',
      approver: session.actor_id,
      decided_at: date,
    };
    snapshot = {
      ...snapshot,
      status: decision === 'approve' ? 'READY' : 'PLANNING',
      approvals: [result],
    };
    return result;
  });
  vi.spyOn(api, 'execute').mockImplementation(async () => {
    snapshot = { ...snapshot, status: 'VERIFYING', receipts: [receipt] };
    return receipt;
  });
  vi.spyOn(api, 'verify').mockImplementation(async () => {
    snapshot = { ...snapshot, verifications: [...snapshot.verifications, verification] };
    return verification;
  });
  vi.spyOn(api, 'segment').mockResolvedValue({
    merchant_id: 'merchant_demo',
    evaluated_at: date,
    inactivity_days: 30,
    histories_analysed: 200,
    inactive_count: 125,
    eligible_count: 120,
    excluded_without_consent: 5,
    excluded_unknown_history: 0,
    recipient_ids: Array.from({ length: 120 }, (_, index) => `customer-${index}`),
    unit_cost_paise: 200,
    estimated_cost_paise: 24000,
    simulated: true,
  } satisfies CustomerSegment);
});
afterEach(() => {
  vi.restoreAllMocks();
});
const showTask = (customSession = session, language: 'en' | 'hi' | 'te' = 'en') =>
  render(
    <TaskWorkspace
      id="task-one"
      session={customSession}
      language={language}
      onTask={() => {}}
      onClose={onClose}
    />,
  );

it('shows server-started work in chat without asking the merchant to create a task', async () => {
  vi.mocked(api.sendMessage).mockImplementationOnce(async (id, content, clientId) => ({
    client_message_id: clientId,
    user_message: {
      ...message('user-linked', content, 'user', 1),
      conversation_id: id,
      task_id: snapshot.task_id,
    },
    assistant_message: {
      ...message('assistant-linked', 'Saved server reply.', 'assistant', 2),
      conversation_id: id,
      task_id: snapshot.task_id,
    },
  }));
  render(<App />);
  await screen.findByRole('heading', { name: 'Hi! How can I help?' });
  expect(screen.getByText('Sharma General Store')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Type a question' }), {
    target: { value: '  Why is my payment short?  ' },
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Saved server reply.');
  expect(api.sendMessage).toHaveBeenCalledWith(
    'chat-2',
    '  Why is my payment short?  ',
    expect.stringMatching(/^ui-/),
  );
  expect(api.createTask).not.toHaveBeenCalled();
  await screen.findByRole('textbox', { name: 'Add clarification' });
  expect(screen.queryByText('Start a task from this question')).toBeNull();
  expect(api.createTask).not.toHaveBeenCalled();
  expect(api.execute).not.toHaveBeenCalled();
  expect(api.resume).not.toHaveBeenCalled();
});

it('keeps ordinary chat as a direct reply without a workflow panel or task prompt', async () => {
  render(<App />);
  fireEvent.change(await screen.findByRole('textbox', { name: 'Type a question' }), {
    target: { value: 'Hello' },
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Saved server reply.');
  expect(screen.queryByText('Start a task from this question')).toBeNull();
  expect(screen.queryByRole('region', { name: 'Task details' })).toBeNull();
  expect(api.createTask).not.toHaveBeenCalled();
  expect(api.task).not.toHaveBeenCalled();
});

it('does not mark a saved message unconfirmed when refreshing its task fails', async () => {
  vi.mocked(api.sendMessage).mockImplementationOnce(async (id, content, clientId) => ({
    client_message_id: clientId,
    user_message: {
      ...message('saved-user', content, 'user', 1),
      conversation_id: id,
      task_id: snapshot.task_id,
    },
    assistant_message: {
      ...message('saved-assistant', 'Confirmed workflow reply.', 'assistant', 2),
      conversation_id: id,
      task_id: snapshot.task_id,
    },
  }));
  vi.mocked(api.task).mockRejectedValue(new ApiError(503, 'UNAVAILABLE', 'Refresh unavailable'));
  render(<App />);
  fireEvent.change(await screen.findByRole('textbox', { name: 'Type a question' }), {
    target: { value: 'Investigate settlement' },
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  await screen.findByText('Confirmed workflow reply.');
  await waitFor(() => expect(api.task).toHaveBeenCalled());
  expect(screen.queryByText('Message not confirmed')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Retry this exact message' })).toBeNull();
  expect(api.sendMessage).toHaveBeenCalledOnce();
});

it('persists the language preference but preserves original saved assistant content and its returned language', async () => {
  history = [message('assistant-en', 'Original English reply', 'assistant', 1)];
  render(<App />);
  const original = await screen.findByText('Original English reply');
  fireEvent.click(screen.getByRole('button', { name: 'Language: English' }));
  fireEvent.click(screen.getByRole('menuitemradio', { name: /Telugu/ }));
  await waitFor(() => expect(api.setLanguage).toHaveBeenCalledWith('chat-2', 'te'));
  expect(original.closest('article')).toHaveAttribute('lang', 'en');
  expect(original).toHaveTextContent('Original English reply');
});

it('ignores late history from a previously selected conversation', async () => {
  let resolveHistory!: (messages: ConversationMessage[]) => void;
  vi.mocked(api.messages).mockImplementation((id) =>
    id === 'chat-2'
      ? new Promise((resolve) => {
          resolveHistory = resolve;
        })
      : Promise.resolve([message('current', 'Current chat history', 'assistant', 1)]),
  );
  render(<App />);
  await screen.findByRole('button', { name: /^Settlement questions/ });
  fireEvent.click(screen.getByRole('button', { name: /^Settlement questions/ }));
  await screen.findByText('Current chat history');
  await act(async () => resolveHistory([message('old', 'Stale response', 'assistant', 1)]));
  expect(screen.queryByText('Stale response')).toBeNull();
});

it('retries an uncertain chat turn with the same content and id and deduplicates saved messages', async () => {
  vi.mocked(api.sendMessage).mockRejectedValueOnce(
    new ApiError(0, 'NETWORK_ERROR', 'Connection lost'),
  );
  render(<App />);
  await screen.findByRole('heading', { name: 'Hi! How can I help?' });
  fireEvent.change(screen.getByRole('textbox', { name: 'Type a question' }), {
    target: { value: 'My payment?' },
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Retry this exact message' }));
  await screen.findByText('Saved server reply.');
  expect(vi.mocked(api.sendMessage).mock.calls[1]).toEqual(
    vi.mocked(api.sendMessage).mock.calls[0],
  );
  expect(screen.getAllByText('My payment?')).toHaveLength(1);
});

it('reopens saved chats and deduplicates ordered history', async () => {
  const saved = message('same', 'One saved message', 'assistant', 1);
  history = [saved, saved];
  const view = render(<App />);
  await screen.findByText('One saved message');
  fireEvent.click(screen.getByRole('button', { name: /^Settlement questions/ }));
  await waitFor(() => expect(api.messages).toHaveBeenCalledWith('chat-1'));
  view.unmount();
  render(<App />);
  await screen.findByText('One saved message');
  expect(screen.getAllByText('One saved message')).toHaveLength(1);
  expect(api.conversation).toHaveBeenLastCalledWith('chat-1');
});

it('shows bootstrap errors with a retry instead of falling back to fabricated records', async () => {
  vi.mocked(api.session).mockRejectedValueOnce(
    new ApiError(403, 'ACCESS_DENIED', 'Merchant access denied'),
  );
  render(<App />);
  await screen.findByText('Merchant access denied');
  expect(screen.queryByText('Sharma General Store')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
  await screen.findByText('Sharma General Store');
});

it('supports clarification without inventing a resumed or completed state', async () => {
  showTask();
  fireEvent.change(await screen.findByRole('textbox', { name: 'Add clarification' }), {
    target: { value: '  Yesterday, please.  ' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save clarification' }));
  await screen.findByText('Yesterday, please.');
  expect(api.clarify).toHaveBeenCalledWith('task-one', '  Yesterday, please.  ');
  expect(screen.getByText('Needs your input')).toBeInTheDocument();
  expect(screen.queryByText('Goal completed')).toBeNull();
});

it('uses the exact server approval snapshot, separates approve/execute, and treats verified=false as unresolved', async () => {
  snapshot = {
    ...snapshot,
    intent: 'settlement',
    status: 'AWAITING_APPROVAL',
    approvals: [structuredClone(approval)],
  };
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
  const execute = await screen.findByRole('button', { name: 'Execute approved action' });
  expect(api.decide).toHaveBeenCalledWith('task-one', approval, 'approve');
  expect(api.execute).not.toHaveBeenCalled();
  fireEvent.click(execute);
  fireEvent.click(execute);
  const verify = await screen.findByRole('button', { name: 'Verify action' });
  expect(api.execute).toHaveBeenCalledTimes(1);
  expect(api.execute).toHaveBeenCalledWith(
    'task-one',
    expect.objectContaining({
      approved_inputs: approval.approved_inputs,
      input_hash: approval.input_hash,
    }),
  );
  fireEvent.click(verify);
  await screen.findByText('Verification failed');
  expect(screen.getByText('Verifying')).toBeInTheDocument();
  expect(screen.queryByText('Goal completed')).toBeNull();
  expect(screen.getByText(/Verified at/)).toBeInTheDocument();
});

it('keeps a verified ticket separate from goal completion and uses the latest verification', async () => {
  snapshot = {
    ...snapshot,
    status: 'VERIFYING',
    receipts: [receipt],
    verifications: [
      { ...verification, verified: true, verified_at: '2026-11-14T07:30:00Z' },
      verification,
    ],
  };
  showTask();
  await screen.findByText('Verification failed');
  expect(screen.queryByText('Action verified')).toBeNull();
  expect(screen.queryByText('Goal completed')).toBeNull();
});

it('can defer approval without sending a request, or cancel using the exact hash', async () => {
  snapshot = { ...snapshot, status: 'AWAITING_APPROVAL', approvals: [approval] };
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Decide later' }));
  expect(onClose).toHaveBeenCalledOnce();
  expect(api.decide).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  await screen.findByText('Cancelled');
  expect(api.decide).toHaveBeenCalledWith('task-one', approval, 'cancel');
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
});

it('reviews an editable campaign using server segmentation and exact audience/cost before approval', async () => {
  snapshot = { ...snapshot, intent: 'win_back', status: 'READY' };
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Find eligible customers' }));
  await screen.findByText(/120 customers who agreed/);
  expect(screen.getByText('₹240.00')).toBeInTheDocument();
  const editor = screen.getByRole('textbox', { name: 'Offer message' });
  fireEvent.change(editor, { target: { value: '  10% off this weekend!  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Review approval' }));
  await screen.findByRole('button', { name: 'Approve' });
  expect(api.requestApproval).toHaveBeenCalledWith(
    'task-one',
    'send_campaign',
    expect.objectContaining({
      task_id: 'task-one',
      message: '  10% off this weekend!  ',
      cost_paise: 24000,
      recipient_ids: expect.any(Array),
    }),
  );
  expect(screen.queryByRole('textbox', { name: 'Offer message' })).toBeNull();
  expect(api.execute).not.toHaveBeenCalled();
});

it('prevents approval and execution when merchant permissions are missing', async () => {
  snapshot = { ...snapshot, status: 'AWAITING_APPROVAL', approvals: [approval] };
  showTask({ ...session, merchant: { ...session.merchant, scopes: ['tasks:read'] } });
  expect(await screen.findByRole('button', { name: 'Approve' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  expect(api.decide).not.toHaveBeenCalled();
});

it('continues managed approvals through orchestration rather than dispatching or verifying independently', async () => {
  snapshot = {
    ...snapshot,
    intent: 'settlement',
    status: 'AWAITING_APPROVAL',
    approvals: [approval],
    workflow_data: { engine_version: 1, phase: 'action', response_language: 'en' },
  };
  vi.mocked(api.resume).mockImplementation(async () => {
    snapshot = {
      ...snapshot,
      status: 'WAITING_EXTERNAL',
      receipts: [receipt],
      verifications: [{ ...verification, verified: true }],
      workflow_data: { ...snapshot.workflow_data, phase: 'finished' },
    };
    return structuredClone(snapshot);
  });
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
  const execute = await screen.findByRole('button', { name: 'Execute approved action' });
  expect(api.resume).not.toHaveBeenCalled();
  fireEvent.click(execute);
  fireEvent.click(execute);
  await screen.findByText('Action verified');
  expect(screen.getByText('Pending externally')).toBeInTheDocument();
  expect(api.resume).toHaveBeenCalledExactlyOnceWith('task-one');
  expect(api.execute).not.toHaveBeenCalled();
  expect(api.verify).not.toHaveBeenCalled();
  expect(screen.queryByText('Goal completed')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Check verification again' })).toBeNull();
});

it('uses persisted task response language even when the conversation preference differs', async () => {
  snapshot = {
    ...snapshot,
    workflow_data: { engine_version: 1, response_language: 'te', phase: 'plan' },
  };
  showTask(session, 'en');
  const clarification = await screen.findByRole('textbox', {
    name: workspaceText('Add clarification', 'te'),
  });
  expect(clarification.closest('section')).toHaveAttribute('lang', 'te');
  expect(screen.getByText(workspaceText('Needs your input', 'te'))).toBeInTheDocument();
});

it('can continue a cancelled managed plan without creating another approval locally', async () => {
  snapshot = {
    ...snapshot,
    status: 'PLANNING',
    approvals: [{ ...approval, decision: 'cancelled' }],
    workflow_data: { engine_version: 1, phase: 'action', response_language: 'en' },
  };
  vi.mocked(api.resume).mockImplementation(async () => {
    snapshot = {
      ...snapshot,
      status: 'AWAITING_INPUT',
      workflow_data: { ...snapshot.workflow_data, phase: 'plan', input_pending: true },
    };
    return structuredClone(snapshot);
  });
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Continue saved task' }));
  await screen.findByRole('textbox', { name: 'Add clarification' });
  expect(api.requestApproval).not.toHaveBeenCalled();
  expect(api.execute).not.toHaveBeenCalled();
});

it('allows completion only when the managed backend returns its completed campaign result', async () => {
  snapshot = {
    ...snapshot,
    intent: 'win_back',
    status: 'COMPLETED',
    next_action: '118 delivered, 2 failed.',
    receipts: [{ ...receipt, action: 'send_campaign' }],
    verifications: [{ ...verification, verified: true }],
    workflow_data: { engine_version: 1, phase: 'finished', response_language: 'en' },
  };
  showTask();
  await screen.findByText('Goal completed');
  expect(screen.getByText('118 delivered, 2 failed.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Continue saved task' })).toBeNull();
});

it.each([ticketFixture, campaignFixture])(
  'renders the supplied READY fixture $task_id without creating a task or executing it',
  async (fixture) => {
    snapshot = {
      ...fixture,
      status: 'READY',
      intent: fixture.intent === 'win_back' ? 'win_back' : 'settlement',
    } as Task;
    showTask();
    await screen.findByRole('heading', { name: 'UI integration fixture' });
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(api.createTask).not.toHaveBeenCalled();
    expect(api.execute).not.toHaveBeenCalled();
  },
);

it('reconciles an uncertain write and never automatically dispatches again', async () => {
  const approved: Approval = {
    ...approval,
    decision: 'approved',
    approver: session.actor_id,
    decided_at: date,
  };
  snapshot = { ...snapshot, intent: 'settlement', status: 'READY', approvals: [approved] };
  vi.mocked(api.execute).mockImplementation(async () => {
    snapshot = {
      ...snapshot,
      status: 'WAITING_EXTERNAL',
      tool_executions: [
        {
          execution_id: 'claim-one',
          task_id: 'task-one',
          merchant_id: 'merchant_demo',
          input_hash: approval.input_hash,
          tool_name: 'create_support_ticket',
          outcome: 'uncertain',
          occurred_at: date,
          error: 'Provider timeout',
        },
      ],
    };
    throw new ApiError(503, 'MOCK_TIMEOUT', 'Provider timeout');
  });
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Execute approved action' }));
  await screen.findByText('Outcome unresolved');
  expect(api.execute).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: 'Execute approved action' })).toBeNull();
});

it.each([
  [403, 'ACCESS_DENIED'],
  [404, 'NOT_FOUND'],
  [409, 'TASK_CONFLICT'],
  [422, 'VALIDATION_ERROR'],
  [503, 'MOCK_TIMEOUT'],
])('shows %s errors and preserves the unsaved clarification', async (status, code) => {
  vi.mocked(api.clarify).mockRejectedValueOnce(
    new ApiError(Number(status), String(code), `Recorded error ${code}`),
  );
  showTask();
  fireEvent.change(await screen.findByRole('textbox', { name: 'Add clarification' }), {
    target: { value: 'Keep this draft' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save clarification' }));
  await screen.findByText(`Recorded error ${code}`);
  expect(screen.getByRole('textbox', { name: 'Add clarification' })).toHaveValue('Keep this draft');
});

it.each(['FAILED', 'ESCALATED', 'WAITING_EXTERNAL', 'COMPLETED'] as const)(
  'renders %s distinctly and deduplicates the timeline',
  async (status) => {
    snapshot = { ...snapshot, status, events: [snapshot.events[0], snapshot.events[0]] };
    showTask();
    await screen.findByText(
      {
        FAILED: 'Failed',
        ESCALATED: 'Escalated to support',
        WAITING_EXTERNAL: 'Pending externally',
        COMPLETED: 'Goal completed',
      }[status],
    );
    const timeline = screen.getByText('Activity timeline').parentElement!;
    expect(within(timeline).getAllByText('No investigation has run.')).toHaveLength(1);
  },
);

it.each(['en', 'hi', 'te'] as const)(
  'formats exact paise and localizes task controls in %s',
  async (language) => {
    expect(paise(16680, language)).toContain('166.80');
    showTask(session, language);
    await screen.findByText(workspaceText('Needs your input', language));
    expect(
      screen.getByRole('textbox', { name: workspaceText('Add clarification', language) }),
    ).toBeInTheDocument();
  },
);

it('continues explicit settlement investigations through their workflow endpoint after approval', async () => {
  snapshot = {
    ...snapshot,
    intent: 'settlement',
    status: 'AWAITING_APPROVAL',
    approvals: [approval],
    workflow_data: { settlement: { phase: 'approval' } },
  };
  showTask();
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
  expect(api.resumeInvestigation).not.toHaveBeenCalled();
  fireEvent.click(await screen.findByRole('button', { name: 'Execute approved action' }));
  await waitFor(() => expect(api.resumeInvestigation).toHaveBeenCalledExactlyOnceWith('task-one'));
  expect(api.execute).not.toHaveBeenCalled();
  expect(api.verify).not.toHaveBeenCalled();
});

it.each(['en', 'hi', 'te'] as const)(
  'labels demo due times in %s and only checks due work on request',
  async (language) => {
    snapshot = {
      ...snapshot,
      intent: 'settlement',
      status: 'WAITING_EXTERNAL',
      schedule_clock: 'demo',
      next_run_at: '2025-01-02T00:00:00Z',
      receipts: [receipt],
      verifications: [{ ...verification, verified: true }],
      workflow_data: { settlement: { phase: 'follow_up' } },
    };
    showTask(session, language);
    await screen.findByText(
      new RegExp(
        workspaceText('Scheduled time (demo clock)', language).replace(
          /[.*+?^${}()|[\]\\]/g,
          '\\$&',
        ),
      ),
    );
    expect(api.runDueSettlements).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: workspaceText('Continue saved task', language) }),
    ).toBeNull();
    const button = screen.getByRole('button', {
      name: workspaceText('Check due follow-ups', language),
    });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(api.runDueSettlements).toHaveBeenCalledOnce());
    await screen.findByText(
      workspaceText('Due follow-ups checked. Review the saved status and evidence.', language),
    );
    expect(screen.queryByText(workspaceText('Goal completed', language))).toBeNull();
    expect(api.execute).not.toHaveBeenCalled();
    expect(api.resumeInvestigation).not.toHaveBeenCalled();
  },
);

it('keeps scheduled follow-ups read-only without the payment permission', async () => {
  snapshot = {
    ...snapshot,
    intent: 'settlement',
    status: 'WAITING_EXTERNAL',
    schedule_clock: 'demo',
    next_run_at: date,
    workflow_data: { settlement: { phase: 'follow_up' } },
  };
  showTask({
    ...session,
    merchant: { ...session.merchant, scopes: ['tasks:read', 'tasks:write'] },
  });
  expect(await screen.findByRole('button', { name: 'Check due follow-ups' })).toBeDisabled();
  expect(api.runDueSettlements).not.toHaveBeenCalled();
});
