import { useState } from 'react';
import type { FormEvent } from 'react';
import { money } from '../demo';
import type { Turn } from '../demo';
import { useLanguage, speechLocales } from '../i18n';
import {
  amountFromQuestion,
  paiseFromInput,
  findCounterPayments,
  existingRefund,
  closingSummary,
  readRefundFollowup,
} from '../paymentDemo';
import { ResponseActivity, replyDelay } from './ResponseActivity';

type Props = { turn: Turn; now: number; reduced: boolean; update: (change: Partial<Turn>) => void };

export function CounterPayment({ turn, now, reduced, update }: Props) {
  const { t, language } = useLanguage();
  const initialAmount = turn.counterQuery?.amount ?? amountFromQuestion(turn.question);
  const [amount, setAmount] = useState(
    initialAmount === undefined ? '' : String(initialAmount / 100),
  );
  const [minutes, setMinutes] = useState(turn.counterQuery?.minutes ?? 15);
  const [minMinutes, setMinMinutes] = useState(turn.counterQuery?.minMinutes ?? 0);
  const [payerName, setPayerName] = useState(turn.counterQuery?.payerName ?? '');
  const [error, setError] = useState(false);
  const query = turn.counterQuery;
  const loading = !!query && now - query.checkedAt < replyDelay;
  const matches = query
    ? findCounterPayments(query.amount, query.minutes, !!turn.counterSettled, {
        ...query,
        settledIds: turn.counterSettledIds,
      })
    : [];
  const selected = turn.counterSelectedId
    ? matches.find((record) => record.id === turn.counterSelectedId)
    : matches.length === 1
      ? matches[0]
      : undefined;
  function search(event: FormEvent) {
    event.preventDefault();
    const paise = paiseFromInput(amount);
    if (!paise) {
      setError(true);
      return;
    }
    setError(false);
    update({
      counterQuery: {
        amount: paise,
        minutes,
        minMinutes,
        payerName: payerName.trim(),
        checkedAt: Date.now(),
      },
      counterSelectedId: undefined,
      counterSettled: false,
      soundboxHelp: false,
    });
  }
  return (
    <section className="card">
      <h2>{t('Payment at the counter')}</h2>
      <p>{t('Match the amount, customer name and approximate payment time.')}</p>
      <form className="record-search" onSubmit={search}>
        <div className="report-fields">
          <label className="report-field">
            {t('Payment amount')}
            <input
              type="number"
              min="0.01"
              step="0.01"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </label>
          <label className="report-field">
            {t('When was it paid?')}
            <select
              value={minMinutes === 5 ? '5-10' : String(minutes)}
              onChange={(event) => {
                setMinMinutes(event.target.value === '5-10' ? 5 : 0);
                setMinutes(event.target.value === '5-10' ? 10 : Number(event.target.value));
              }}
            >
              <option value="5-10">{t('5–10 minutes ago')}</option>
              {[5, 10, 15, 30, 60, 120].map((value) => (
                <option key={value} value={value}>
                  {value} {t('minutes ago or less')}
                </option>
              ))}
            </select>
          </label>
          <label className="report-field">
            {t('Customer name (optional)')}
            <input
              type="text"
              maxLength={100}
              value={payerName}
              placeholder={t('For example, Saiteja')}
              onChange={(event) => setPayerName(event.target.value)}
            />
          </label>
        </div>
        {error && <p role="alert">{t('Enter a valid amount.')}</p>}
        <button type="submit" className="secondary" disabled={loading}>
          {t('Search payment records')}
        </button>
      </form>
      {loading && (
        <ResponseActivity
          elapsed={Math.max(0, now - query!.checkedAt)}
          duration={replyDelay}
          reduced={reduced}
        />
      )}
      {query && !loading && (
        <div className="check-result">
          {!matches.length && (
            <p role="status">
              <strong>{t('Couldn’t find a matching payment')}</strong>
            </p>
          )}
          {matches.length > 1 && (
            <p>
              {t(
                'Several payments match. Compare the customer name and time, then select the right payment.',
              )}
            </p>
          )}
          {matches.map((record) => (
            <div
              className="payment-match"
              key={record.id}
              data-selected={selected?.id === record.id}
            >
              <div className="record-status" data-status={record.status}>
                <strong role="status">{t(record.status)}</strong>
                <span>{money(record.paise)}</span>
              </div>
              <p className="payment-payer">
                <span>{t('From')}</span>{' '}
                <strong>{record.payerName ?? t('Name unavailable')}</strong>
              </p>
              <p className="fine">
                {new Intl.RelativeTimeFormat(speechLocales[language], { numeric: 'always' }).format(
                  -record.minutesAgo,
                  'minute',
                )}
                {' · '}
                {new Intl.DateTimeFormat(speechLocales[language], {
                  hour: 'numeric',
                  minute: '2-digit',
                  timeZone: 'Asia/Kolkata',
                }).format(new Date(query.checkedAt - record.minutesAgo * 60000))}
              </p>
              {matches.length > 1 && (
                <button
                  type="button"
                  className="secondary"
                  aria-pressed={selected?.id === record.id}
                  aria-label={`${t('Select payment')} · ${record.payerName ?? t('Name unavailable')} · ${money(record.paise)}`}
                  onClick={() => update({ counterSelectedId: record.id, soundboxHelp: false })}
                >
                  {t(selected?.id === record.id ? 'Selected payment' : 'Select payment')}
                </button>
              )}
              <details>
                <summary>{t('View details')}</summary>
                <p className="fine">
                  {t('Sample payment record')} · {record.id}
                </p>
              </details>
            </div>
          ))}
          {selected?.status === 'Received' && (
            <button
              className="secondary"
              type="button"
              onClick={() => update({ soundboxHelp: true })}
            >
              {t('Get Soundbox help')}
            </button>
          )}
          {matches.some((record) => record.status === 'Pending') && (
            <button
              className="secondary"
              type="button"
              onClick={() =>
                update({
                  counterSettled: false,
                  counterSettledIds: [
                    ...new Set([
                      ...(turn.counterSettledIds ?? []),
                      ...matches
                        .filter((record) => record.status === 'Pending')
                        .map((record) => record.id),
                    ]),
                  ],
                  counterQuery: { ...query, checkedAt: Date.now() },
                })
              }
            >
              {t('Run simulated payment update')}
            </button>
          )}
          {turn.soundboxHelp && selected?.status === 'Received' && (
            <p className="device-help">
              {t(
                'The payment is confirmed in the record. You can check your Soundbox alerts next.',
              )}{' '}
              <a
                href="https://business.paytm.com/support/paytm-soundbox"
                target="_blank"
                rel="noreferrer"
              >
                {t('Paytm Soundbox help')}
              </a>
            </p>
          )}
          {!matches.length && (
            <p className="fine">
              {t(
                'Try another amount, customer name or time window. The current records do not confirm this payment.',
              )}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

export function RefundFollowup({ turn, now, reduced, update }: Props) {
  const { t } = useLanguage();
  const [amount, setAmount] = useState(
    String((turn.refundQuery?.amount ?? amountFromQuestion(turn.question) ?? 65000) / 100),
  );
  const query = turn.refundQuery;
  const loading = !!query && now - query.checkedAt < replyDelay;
  const found = query?.amount === existingRefund.amount;
  const reference = 'BM-' + turn.id.slice(0, 8).toUpperCase();
  function search(event: FormEvent) {
    event.preventDefault();
    const paise = paiseFromInput(amount);
    if (paise) update({ refundQuery: { amount: paise, checkedAt: Date.now() } });
  }
  return (
    <section className="card">
      <h2>{t('Refund follow-up')}</h2>
      <p>{t('I will check the original payment and the existing refund first.')}</p>
      <form className="record-search" onSubmit={search}>
        <label className="report-field">
          {t('Refund amount')}
          <input
            type="number"
            min="0.01"
            step="0.01"
            required
            readOnly={!!turn.approvedAt}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <button className="secondary" type="submit" disabled={loading || !!turn.approvedAt}>
          {t('Check existing refund')}
        </button>
      </form>
      {loading && (
        <ResponseActivity
          elapsed={Math.max(0, now - query!.checkedAt)}
          duration={replyDelay}
          reduced={reduced}
        />
      )}
      {query && !loading && !found && (
        <p className="check-result" role="status">
          {t('Couldn’t find a matching refund. Check the amount and try again.')}
        </p>
      )}
      {query && !loading && found && (
        <div className="check-result">
          <div
            className="record-status"
            data-status={turn.action === 'verified' ? 'Received' : 'Pending'}
          >
            <strong role="status">
              {t(turn.action === 'verified' ? 'Refund credited' : 'Refund pending')}
            </strong>
            <span>{money(existingRefund.amount)}</span>
          </div>
          <p>
            {t(
              turn.action === 'verified'
                ? 'A fresh sample refund record confirms the credit to the customer.'
                : 'The existing refund is pending with the bank. The refund record does not yet confirm customer credit.',
            )}
          </p>
          <details>
            <summary>{t('View details')}</summary>
            <dl className="breakdown">
              <div>
                <dt>{t('Original payment')}</dt>
                <dd>{existingRefund.paymentId}</dd>
              </div>
              <div>
                <dt>{t('Refund reference')}</dt>
                <dd>{existingRefund.id}</dd>
              </div>
              <div>
                <dt>{t('Bank reference')}</dt>
                <dd>{existingRefund.bankReference}</dd>
              </div>
            </dl>
          </details>
          {!turn.action && (
            <button type="button" className="primary" onClick={() => update({ action: 'confirm' })}>
              {t('Follow up on this refund')}
            </button>
          )}
          {turn.action === 'confirm' && (
            <div className="inline-approval">
              <h3>{t('Create a support request?')}</h3>
              <p>
                {t(
                  'Share the existing refund reference and pending status with simulated support.',
                )}
              </p>
              <div className="actions">
                <button
                  className="primary"
                  type="button"
                  onClick={() => update({ action: 'pending', approvedAt: Date.now() })}
                >
                  {t('Confirm support request')}
                </button>
                <button
                  className="secondary"
                  type="button"
                  onClick={() => update({ action: undefined })}
                >
                  {t('Cancel')}
                </button>
              </div>
            </div>
          )}
          {turn.approvedAt && (
            <div className="inline-approval">
              <p role="status">
                {t(
                  turn.action === 'verified'
                    ? 'Refund follow-up finished'
                    : 'Pending with support.',
                )}
              </p>
              <details>
                <summary>{t('View details')}</summary>
                <p>
                  {t('Simulated ticket')} · {reference}
                </p>
              </details>
              {turn.action === 'pending' && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    const fresh = readRefundFollowup(turn);
                    if (fresh?.refundId === existingRefund.id && fresh.amount === query.amount)
                      update({
                        action: 'verified',
                        refundQuery: { ...query, checkedAt: Date.now() },
                      });
                  }}
                >
                  {t('Run simulated refund update')}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export function DailyClosing({
  turn,
  onQuestion,
}: {
  turn: Turn;
  onQuestion: (question: string) => void;
}) {
  const { t, language } = useLanguage();
  const date = new Intl.DateTimeFormat(speechLocales[language], {
    dateStyle: 'medium',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(turn.started));
  return (
    <section className="card">
      <h2>{t('Daily closing')}</h2>
      <p className="fine">
        {date} · {t('Sample records up to the time of your request')}
      </p>
      <dl className="closing-totals">
        {[
          ['Paytm collections', closingSummary.collections],
          ['Refunds recorded', closingSummary.refunds],
          ['Bank transfers received', closingSummary.bankTransfers],
        ].map(([label, amount]) => (
          <div key={label}>
            <dt>{t(String(label))}</dt>
            <dd>{money(Number(amount))}</dd>
          </div>
        ))}
      </dl>
      <p>
        {t(
          'Collections, refunds and bank credits cover records posted on this day. Bank transfers can include earlier collections.',
        )}
      </p>
      <details>
        <summary>{t('View details')}</summary>
        <p className="fine">
          {t(
            'Payments marked received, refunds recorded, and bank credits posted between midnight and this check.',
          )}{' '}
          · COLLECTIONS-DAY / RF-650-001 / BANK-POSTED-DAY
        </p>
      </details>
      <button
        type="button"
        className="secondary"
        onClick={() => onQuestion(t('Review my sales report.'))}
      >
        {t('Review another sales period')}
      </button>
    </section>
  );
}
