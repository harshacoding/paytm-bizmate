import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type {
  Approval,
  CustomerSegment,
  LanguageCode,
  Session,
  Task,
  TaskEvent,
} from '../api/types';
import { translate } from '../i18n';
import { initialOffer } from '../demo';
import { errorText } from '../useWorkspace';
import { workspaceText } from '../workspaceText';
import { SettlementEvidence } from './SettlementEvidence';
import { paise, stamp } from '../api/format';

const statuses = {
  CREATED: 'Saved',
  PLANNING: 'Planning',
  READY: 'Ready',
  RUNNING: 'Executing',
  AWAITING_INPUT: 'Needs your input',
  AWAITING_APPROVAL: 'Needs approval',
  WAITING_EXTERNAL: 'Pending externally',
  VERIFYING: 'Verifying',
  COMPLETED: 'Goal completed',
  ESCALATED: 'Escalated to support',
  FAILED: 'Failed',
};
export const taskLabel = (task: Task, language: LanguageCode) =>
  workspaceText(statuses[task.status], language);
const sameAction = (approval: Approval, task: Task) =>
  task.receipts.some(
    (receipt) => receipt.input_hash === approval.input_hash && receipt.action === approval.action,
  );
const unresolvedClaim = (task: Task) =>
  task.tool_executions.some(
    (execution) =>
      execution.outcome === 'uncertain' &&
      !task.receipts.some((receipt) => receipt.input_hash === execution.input_hash),
  );

export function TaskWorkspace({
  id,
  session,
  language,
  onTask,
  onClose,
}: {
  id: string;
  session: Session;
  language: LanguageCode;
  onTask: (task: Task) => void;
  onClose: () => void;
}) {
  const t = (text: string) => workspaceText(text, language);
  const [task, setTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [clarification, setClarification] = useState('');
  const [editor, setEditor] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [segment, setSegment] = useState<CustomerSegment | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const currentId = useRef(id);
  const mutationLock = useRef(false);
  const generation = useRef(0);
  const snapshotRevision = useRef(-1);
  const onTaskRef = useRef(onTask);
  onTaskRef.current = onTask;
  const has = (...scopes: string[]) =>
    scopes.every((scope) => session.merchant.scopes.some((value) => value === scope));
  const canWrite = has('tasks:read', 'tasks:write');

  const refresh = useCallback(async (reportError = true) => {
    const requestId = currentId.current;
    const requestGeneration = generation.current;
    try {
      const [snapshot, timeline] = await Promise.all([api.task(requestId), api.events(requestId)]);
      if (requestId !== currentId.current || requestGeneration !== generation.current) return;
      if (snapshot.revision < snapshotRevision.current) return;
      snapshotRevision.current = snapshot.revision;
      setTask((previous) =>
        previous && previous.revision > snapshot.revision ? previous : snapshot,
      );
      setEvents([...new Map(timeline.map((event) => [event.event_id, event])).values()]);
      onTaskRef.current(snapshot);
      setUncertain(unresolvedClaim(snapshot));
      if (reportError) setError('');
      return snapshot;
    } catch (failure) {
      if (requestGeneration === generation.current && reportError) setError(errorText(failure));
    }
  }, []);

  useEffect(() => {
    currentId.current = id;
    generation.current++;
    snapshotRevision.current = -1;
    setTask(null);
    setError('');
    setNotice('');
    setClarification('');
    setEditor(null);
    setSegment(null);
    setUncertain(false);
    void refresh();
    let interval: number | undefined;
    const schedule = () => {
      window.clearInterval(interval);
      if (!document.hidden) {
        void refresh(false);
        interval = window.setInterval(() => {
          if (!mutationLock.current) void refresh(false);
        }, 2000);
      }
    };
    schedule();
    document.addEventListener('visibilitychange', schedule);
    return () => {
      generation.current++;
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', schedule);
    };
  }, [id, refresh]);

  async function mutate(operation: () => Promise<unknown>, success: string, mayDispatch = true) {
    if (mutationLock.current) return;
    mutationLock.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    const requestGeneration = generation.current;
    try {
      await operation();
      if (requestGeneration !== generation.current) return;
      setNotice(success);
      await refresh(false);
    } catch (failure) {
      if (requestGeneration !== generation.current) return;
      setError(errorText(failure));
      if (
        mayDispatch &&
        (!(failure instanceof ApiError) || failure.status === 0 || failure.status >= 500)
      )
        setUncertain(true);
      // Reconcile authoritative state after any conflict or uncertain mutation; never redispatch.
      await refresh(false);
    } finally {
      mutationLock.current = false;
      if (requestGeneration === generation.current) setBusy(false);
    }
  }

  if (!task)
    return (
      <section className="api-task card" aria-label={t('Task details')}>
        <button className="secondary" onClick={onClose}>
          {t('Back to chat')}
        </button>
        {error ? (
          <div role="alert">
            <p>{error}</p>
            <button className="secondary" onClick={() => void refresh()}>
              {t('Refresh')}
            </button>
          </div>
        ) : (
          <p role="status">{t('Loading task…')}</p>
        )}
      </section>
    );
  const campaign = task.intent === 'win_back';
  const action = campaign ? 'send_campaign' : 'create_support_ticket';
  const actionScopes = campaign ? ['campaigns:write', 'customers:read'] : ['tickets:write'];
  const canAction = canWrite && has(...actionScopes);
  const canApprove = canAction && has('tasks:approve');
  const pending = task.approvals.find((approval) => approval.decision === 'pending');
  const approvedUnsent = task.approvals.some(
    (approval) => approval.decision === 'approved' && !sameAction(approval, task),
  );
  const editable =
    ['READY', 'RUNNING'].includes(task.status) &&
    !pending &&
    !approvedUnsent &&
    !unresolvedClaim(task) &&
    !uncertain;
  const actionSupported = ['settlement', 'handoff', 'win_back'].includes(task.intent);
  const latestVerifications = new Map<string, Task['verifications'][number]>();
  for (const verification of task.verifications) {
    const previous = latestVerifications.get(verification.receipt_id);
    if (!previous || new Date(verification.verified_at) >= new Date(previous.verified_at))
      latestVerifications.set(verification.receipt_id, verification);
  }
  const text = editor ?? (campaign ? translate(initialOffer, language) : task.goal);

  return (
    <section className="api-task card" aria-label={t('Task details')} lang={language}>
      <div className="api-section-heading">
        <button className="api-back" onClick={onClose}>
          ← {t('Back to chat')}
        </button>
        <button className="secondary" disabled={busy} onClick={() => void refresh()}>
          {t('Refresh')}
        </button>
      </div>
      <span className="api-eyebrow">
        {task.simulated ? t('Synthetic data · Simulated actions') : t('Task details')}
      </span>
      <h2>{task.goal}</h2>
      <span
        className={`api-status status-${task.status.toLowerCase()}`}
        role="status"
        aria-live="polite"
      >
        {taskLabel(task, language)}
      </span>
      <div className="api-next">
        <strong>{t('Next action')}</strong>
        <p>{task.next_action}</p>
        {task.next_run_at && (
          <small>
            {t('Scheduled time')} · {stamp(task.next_run_at, language)} ·{' '}
            {t('Execution is not guaranteed by this timestamp.')}
          </small>
        )}
      </div>
      <div className="api-task-announcement" role="status" aria-live="polite">
        {notice}
      </div>
      {error && (
        <div className="api-error" role="alert">
          <strong>{t('Action needs attention')}</strong>
          <p>{error}</p>
          <p>{t('Refresh saved records before trying another action.')}</p>
        </div>
      )}
      {(uncertain || unresolvedClaim(task) || task.status === 'WAITING_EXTERNAL') && (
        <div className="api-warning">
          <strong>{t('Outcome unresolved')}</strong>
          <p>
            {t(
              'Do not resend. A request may already have reached the provider. Refresh the task and inspect its receipt.',
            )}
          </p>
        </div>
      )}

      {task.status === 'AWAITING_INPUT' && (
        <form
          className="api-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (clarification.trim())
              void mutate(async () => {
                await api.clarify(id, clarification);
                setClarification('');
              }, t('Clarification saved. The backend will determine the next step.'));
          }}
        >
          <label htmlFor="task-clarification">{t('Add clarification')}</label>
          <textarea
            id="task-clarification"
            value={clarification}
            maxLength={4000}
            onChange={(event) => setClarification(event.target.value)}
            disabled={!canWrite || busy}
          />
          <button className="primary" disabled={!canWrite || busy || !clarification.trim()}>
            {t('Save clarification')}
          </button>
          <small>{t('Saving a clarification does not mean execution has resumed.')}</small>
        </form>
      )}

      {task.intent === 'settlement' && (
        <SettlementEvidence language={language} allowed={has('payments:read')} />
      )}
      {task.evidence.length > 0 && (
        <section className="api-evidence">
          <h3>{t('Financial evidence')}</h3>
          {task.evidence.map((evidence) => (
            <article key={evidence.evidence_id} className="api-proof">
              <p>{evidence.description}</p>
              {evidence.amount_paise !== null && (
                <strong>{paise(evidence.amount_paise, language)}</strong>
              )}
              <small>
                {t('Captured')} · {stamp(evidence.captured_at, language)}
              </small>
              <details>
                <summary>{t('View details')}</summary>
                <p>{evidence.source}</p>
                <code>{evidence.source_reference}</code>
              </details>
            </article>
          ))}
        </section>
      )}

      {actionSupported && editable && (
        <section className="api-action-editor">
          <h3>{campaign ? t('Review your offer') : t('Prepare support request')}</h3>
          {campaign && (
            <div className="api-segment">
              <label>
                {t('Days since last visit')}
                <input
                  aria-label={t('Days since last visit')}
                  type="number"
                  min="1"
                  max="3650"
                  value={days}
                  onChange={(event) => {
                    setDays(Number(event.target.value));
                    setSegment(null);
                  }}
                  disabled={busy}
                />
              </label>
              <button
                className="secondary"
                disabled={!canAction || busy || !Number.isInteger(days) || days < 1 || days > 3650}
                onClick={() =>
                  void mutate(
                    async () => {
                      setSegment(await api.segment(days));
                    },
                    t('Eligible audience loaded'),
                    false,
                  )
                }
              >
                {t('Find eligible customers')}
              </button>
              {segment && (
                <div>
                  <strong>
                    {segment.eligible_count} {t('customers who agreed to receive offers')}
                  </strong>
                  <p>
                    {t('Estimated cost')} <b>{paise(segment.estimated_cost_paise, language)}</b>
                  </p>
                  <small>
                    {t('Evaluated')} · {stamp(segment.evaluated_at, language)}
                  </small>
                  <details>
                    <summary>{t('View details')}</summary>
                    <p>
                      {t('Histories reviewed')}: {segment.histories_analysed}
                    </p>
                    <p>
                      {t('Excluded without consent')}: {segment.excluded_without_consent}
                    </p>
                  </details>
                </div>
              )}
            </div>
          )}
          <form
            className="api-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!text.trim()) return;
              const inputs = campaign
                ? {
                    task_id: id,
                    message: text,
                    recipient_ids: segment!.recipient_ids,
                    cost_paise: segment!.estimated_cost_paise,
                  }
                : { task_id: id, summary: text };
              void mutate(
                () => api.requestApproval(id, action, inputs),
                t('Approval snapshot saved. Review it before approving.'),
              );
            }}
          >
            <label htmlFor="action-message">
              {campaign ? t('Offer message') : t('Support summary')}
            </label>
            <textarea
              id="action-message"
              value={text}
              onChange={(event) => setEditor(event.target.value)}
              maxLength={4000}
              disabled={!canAction || busy}
            />
            <p>
              {campaign
                ? t('No campaign is sent until you approve and execute the saved offer and cost.')
                : t(
                    'This will create a simulated support ticket. It will not prove a missing bank credit arrived.',
                  )}
            </p>
            <button
              className="primary"
              disabled={
                !canAction ||
                busy ||
                !text.trim() ||
                (campaign && (!segment || segment.eligible_count === 0))
              }
            >
              {t('Review approval')}
            </button>
          </form>
        </section>
      )}

      {task.approvals.map((approval) => {
        const executed = sameAction(approval, task);
        const campaignApproval = approval.action === 'send_campaign';
        const canDecideThis =
          canWrite &&
          has(
            'tasks:approve',
            ...(approval.decision === 'pending'
              ? campaignApproval
                ? ['campaigns:write', 'customers:read']
                : ['tickets:write']
              : []),
          );
        const claimed = task.tool_executions.some(
          (execution) => execution.input_hash === approval.input_hash,
        );
        return (
          <article className="api-approval" key={approval.approval_id}>
            <div className="api-section-heading">
              <h3>{t('Approval snapshot')}</h3>
              <span className="api-status">
                {t(
                  approval.decision === 'pending'
                    ? 'Pending approval'
                    : approval.decision === 'approved'
                      ? 'Approved'
                      : 'Cancelled',
                )}
              </span>
            </div>
            <p className="api-snapshot-text">
              {String(approval.approved_inputs.message ?? approval.approved_inputs.summary ?? '')}
            </p>
            {campaignApproval && (
              <dl className="api-amounts">
                <div>
                  <dt>{t('Recipients')}</dt>
                  <dd>
                    {Array.isArray(approval.approved_inputs.recipient_ids)
                      ? approval.approved_inputs.recipient_ids.length
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt>{t('Estimated cost')}</dt>
                  <dd>
                    {typeof approval.approved_inputs.cost_paise === 'number'
                      ? paise(approval.approved_inputs.cost_paise, language)
                      : '—'}
                  </dd>
                </div>
              </dl>
            )}
            <p className="api-disclaimer">
              {campaignApproval
                ? t(
                    'Approval authorises this exact offer, audience and cost. Sending and verification are separate steps.',
                  )
                : t(
                    'Approval authorises this exact support summary. A ticket is not proof that the merchant issue is resolved.',
                  )}
            </p>
            {approval.decided_at && (
              <small>
                {t('Decision recorded')} · {stamp(approval.decided_at, language)}
              </small>
            )}
            <details>
              <summary>{t('View details')}</summary>
              <code>{approval.approval_id}</code>
              <p>{t('Exact input hash')}</p>
              <code>{approval.input_hash}</code>
              <pre>{JSON.stringify(approval.approved_inputs, null, 2)}</pre>
            </details>
            <div className="api-actions">
              {approval.decision === 'pending' && (
                <>
                  <button
                    className="primary"
                    disabled={!canDecideThis || !canApprove || busy}
                    onClick={() =>
                      void mutate(
                        () => api.decide(id, approval, 'approve'),
                        t('Approved. Execution has not started.'),
                      )
                    }
                  >
                    {t('Approve')}
                  </button>
                  <button
                    className="secondary"
                    disabled={!canWrite || !has('tasks:approve') || busy}
                    onClick={() =>
                      void mutate(
                        () => api.decide(id, approval, 'cancel'),
                        t('Cancelled. Replanning must be handled by the backend.'),
                      )
                    }
                  >
                    {t('Cancel')}
                  </button>
                  <button className="api-back" onClick={onClose} disabled={busy}>
                    {t('Decide later')}
                  </button>
                </>
              )}
              {approval.decision === 'approved' &&
                !executed &&
                !claimed &&
                !uncertain &&
                ['READY', 'RUNNING'].includes(task.status) && (
                  <button
                    className="primary"
                    disabled={
                      !canAction || !canApprove || approval.approver !== session.actor_id || busy
                    }
                    onClick={() =>
                      void mutate(
                        () => api.execute(id, approval),
                        t('Action executed. Independent verification is still required.'),
                      )
                    }
                  >
                    {t('Execute approved action')}
                  </button>
                )}
              {approval.decision === 'approved' && !executed && !claimed && (
                <button
                  className="secondary"
                  disabled={!canWrite || !has('tasks:approve') || busy}
                  onClick={() =>
                    void mutate(
                      () => api.decide(id, approval, 'cancel'),
                      t('Cancelled. Replanning must be handled by the backend.'),
                    )
                  }
                >
                  {t('Cancel')}
                </button>
              )}
            </div>
          </article>
        );
      })}

      {task.receipts.length > 0 && (
        <section>
          <h3>{t('Execution receipts')}</h3>
          {task.receipts.map((receipt) => {
            const verification = latestVerifications.get(receipt.receipt_id);
            const verifierScope =
              receipt.action === 'send_campaign' ? 'campaigns:write' : 'tickets:write';
            return (
              <article className="api-receipt" key={receipt.receipt_id}>
                <div className="api-section-heading">
                  <strong>{t('Executed')}</strong>
                  <span
                    className={`api-status ${verification?.verified === false ? 'status-failed' : ''}`}
                  >
                    {t(
                      !verification
                        ? 'Not verified'
                        : verification.verified
                          ? 'Action verified'
                          : 'Verification failed',
                    )}
                  </span>
                </div>
                <p>
                  {receipt.action === 'send_campaign'
                    ? t('Campaign reference')
                    : t('Ticket reference')}
                  : <b>{receipt.external_reference}</b>
                </p>
                <small>
                  {t('Executed at')} · {stamp(receipt.created_at, language)}
                </small>
                {verification && (
                  <p>
                    <small>
                      {t('Verified at')} · {stamp(verification.verified_at, language)}
                    </small>
                  </p>
                )}
                <p className="api-disclaimer">
                  {t(
                    'A verified action does not mean the task goal is complete. Follow the backend task status and next action.',
                  )}
                </p>
                <details>
                  <summary>{t('View details')}</summary>
                  <code>{receipt.receipt_id}</code>
                  <p>{receipt.idempotency_key}</p>
                  {verification && <p>{verification.evidence_reference}</p>}
                </details>
                <button
                  className="secondary"
                  disabled={!canWrite || !has(verifierScope) || busy}
                  onClick={() =>
                    void mutate(
                      async () => {
                        const result = await api.verify(id, receipt.receipt_id);
                        if (!result.verified)
                          setError(
                            t(
                              'Verification did not confirm the action. The work remains unresolved.',
                            ),
                          );
                      },
                      t('Verification attempt recorded'),
                      false,
                    )
                  }
                >
                  {t(verification ? 'Check verification again' : 'Verify action')}
                </button>
              </article>
            );
          })}
        </section>
      )}

      {task.capability_gaps.length > 0 && (
        <section>
          <h3>{t('Support handoff')}</h3>
          {task.capability_gaps.map((gap) => (
            <article className="api-warning" key={gap.gap_id}>
              <strong>{gap.requested_capability}</strong>
              <p>{gap.reason}</p>
              <p>{t('Pending with support.')}</p>
              {gap.handoff_reference && (
                <p>
                  {t('Ticket reference')}: {gap.handoff_reference}
                </p>
              )}
            </article>
          ))}
        </section>
      )}
      <details className="api-timeline" open>
        <summary>{t('Activity timeline')}</summary>
        {events.length === 0 ? (
          <p>{t('No activity recorded yet.')}</p>
        ) : (
          <ol>
            {events.map((event) => (
              <li key={event.event_id}>
                <p>{event.message}</p>
                <time dateTime={event.occurred_at}>{stamp(event.occurred_at, language)}</time>
              </li>
            ))}
          </ol>
        )}
      </details>
      {task.plan.length > 0 && (
        <details>
          <summary>{t('Plan progress')}</summary>
          <ol className="api-plan">
            {task.plan.map((step) => (
              <li key={step.step_id}>
                <span className="api-status">
                  {t(
                    step.status === 'done'
                      ? 'Done'
                      : step.status === 'running'
                        ? 'Checking'
                        : step.status === 'failed'
                          ? 'Failed'
                          : 'Next',
                  )}
                </span>
                <code>{step.tool_name}</code>
              </li>
            ))}
          </ol>
        </details>
      )}
      <details>
        <summary>{t('View details')}</summary>
        <p>
          {t('Task reference')}: <code>{task.task_id}</code>
        </p>
        <p>
          {t('Revision')}: {task.revision}
        </p>
        <p>
          {t('Updated')}: {stamp(task.updated_at, language)}
        </p>
        <p>{task.original_request}</p>
      </details>
      {!canWrite && <p role="status">{t('Your merchant permissions allow viewing only.')}</p>}
      {canWrite && actionSupported && (!canAction || !has('tasks:approve')) && (
        <p role="status">
          {t('Your permissions do not allow this action. Contact merchant support.')}
        </p>
      )}
    </section>
  );
}
