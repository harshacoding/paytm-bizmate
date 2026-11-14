import { useState } from 'react';
import type { FormEvent } from 'react';
import { money } from '../demo';
import type { Turn } from '../demo';
import { speechLocales, useLanguage } from '../i18n';
import { ResponseActivity, replyDelay } from './ResponseActivity';

export type SalesPeriod = { start: string; end: string };
type PeriodMode = 'today' | 'date' | 'month' | 'range';
const dayMs = 86400000;
export function merchantToday() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}
export function validPeriod(period: SalesPeriod, today: string) {
  const validDate = (date: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    Number.isFinite(Date.parse(date)) &&
    new Date(date).toISOString().slice(0, 10) === date;
  return (
    validDate(period.start) &&
    validDate(period.end) &&
    period.start <= period.end &&
    period.end <= today
  );
}
export function sampleSales(period: SalesPeriod) {
  let gross = 0,
    refunds = 0,
    payments = 0;
  const start = Date.parse(period.start) / dayMs;
  const end = Date.parse(period.end) / dayMs;
  for (let day = start; day <= end; day++) {
    const seed = Math.abs(day);
    const count = 35 + (seed % 31);
    gross += count * (18000 + (seed % 13) * 950);
    payments += count;
    refunds += (seed % 4) * 15000;
  }
  const upi = Math.floor((gross * 70) / 100);
  const cards = Math.floor((gross * 20) / 100);
  return { gross, refunds, payments, net: gross - refunds, upi, cards, cash: gross - upi - cards };
}

export function SalesReport({
  turn,
  now,
  reduced,
  update,
}: {
  turn: Turn;
  now: number;
  reduced: boolean;
  update: (change: Partial<Turn>) => void;
}) {
  const { t, language } = useLanguage();
  const today = merchantToday();
  const [mode, setMode] = useState<PeriodMode>(turn.salesMode ?? 'today');
  const [date, setDate] = useState(turn.salesPeriod?.start ?? today);
  const [start, setStart] = useState(turn.salesPeriod?.start ?? today.slice(0, 8) + '01');
  const [end, setEnd] = useState(turn.salesPeriod?.end ?? today);
  const [year, setYear] = useState(Number((turn.salesPeriod?.start ?? today).slice(0, 4)));
  const [month, setMonth] = useState(Number((turn.salesPeriod?.start ?? today).slice(5, 7)));
  const [error, setError] = useState(false);
  const currentYear = Number(today.slice(0, 4));
  const currentMonth = Number(today.slice(5, 7));
  const loading = !!turn.reportRequestedAt && now - turn.reportRequestedAt < replyDelay;
  const period = turn.salesPeriod;
  const report = period && !loading && validPeriod(period, today) ? sampleSales(period) : null;
  const formatDate = (date: string) =>
    new Intl.DateTimeFormat(speechLocales[language], {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(date));

  function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let selected = { start, end };
    if (mode === 'today') selected = { start: today, end: today };
    if (mode === 'date') selected = { start: date, end: date };
    if (mode === 'month') {
      const first = year + '-' + String(month).padStart(2, '0') + '-01';
      const last = new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
      selected = { start: first, end: last > today ? today : last };
    }
    if (!validPeriod(selected, today)) {
      setError(true);
      return;
    }
    setError(false);
    update({ salesPeriod: selected, salesMode: mode, reportRequestedAt: Date.now() });
  }

  return (
    <section className="card sales-card">
      <h2>{t('Sales report')}</h2>
      <p>{t('Which period would you like to review?')}</p>
      <form onSubmit={generate}>
        <fieldset className="period-picker">
          <legend className="sr-only">{t('Report period')}</legend>
          {(['today', 'date', 'month', 'range'] as const).map((value, index) => (
            <label key={value} data-selected={mode === value}>
              <input
                type="radio"
                name={'period-' + turn.id}
                value={value}
                checked={mode === value}
                onChange={() => {
                  setMode(value);
                  setError(false);
                }}
              />
              {t(['Today', 'Select date', 'Monthly', 'Date range'][index])}
            </label>
          ))}
        </fieldset>
        {mode === 'date' && (
          <label className="report-field">
            {t('Select date')}
            <input
              type="date"
              required
              max={today}
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
        )}
        {mode === 'month' && (
          <div className="report-fields">
            <label className="report-field">
              {t('Month')}
              <select value={month} onChange={(event) => setMonth(Number(event.target.value))}>
                {Array.from({ length: 12 }, (_, i) => (
                  <option
                    key={i}
                    value={i + 1}
                    disabled={year === currentYear && i + 1 > currentMonth}
                  >
                    {new Intl.DateTimeFormat(speechLocales[language], {
                      month: 'long',
                      timeZone: 'UTC',
                    }).format(new Date(Date.UTC(2024, i, 1)))}
                  </option>
                ))}
              </select>
            </label>
            <label className="report-field">
              {t('Year')}
              <select
                value={year}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  setYear(next);
                  if (next === currentYear && month > currentMonth) setMonth(currentMonth);
                }}
              >
                {Array.from({ length: 7 }, (_, i) => currentYear - i).map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          </div>
        )}
        {mode === 'range' && (
          <div className="report-fields">
            <label className="report-field">
              {t('From date')}
              <input
                type="date"
                required
                max={today}
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label className="report-field">
              {t('To date')}
              <input
                type="date"
                required
                max={today}
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </label>
          </div>
        )}
        {error && (
          <p className="report-error" role="alert">
            {t('Choose a valid period ending on or before today. The start date must come first.')}
          </p>
        )}
        <button className="primary" type="submit" disabled={loading}>
          {t(loading ? 'Preparing report…' : 'View sales report')}
        </button>
      </form>
      {loading && (
        <ResponseActivity
          elapsed={Math.max(0, now - turn.reportRequestedAt!)}
          duration={replyDelay}
          reduced={reduced}
        />
      )}
      {report && period && (
        <div className="sales-result" role="status">
          <h3>{t('Your sample sales report')}</h3>
          <p className="fine">
            {formatDate(period.start)} — {formatDate(period.end)}
          </p>
          <dl className="totals">
            <div>
              <dt>{t('Total sales')}</dt>
              <dd>{money(report.gross)}</dd>
            </div>
            <div>
              <dt>{t('Net sales')}</dt>
              <dd>{money(report.net)}</dd>
            </div>
          </dl>
          <dl className="breakdown">
            <div>
              <dt>{t('Successful payments')}</dt>
              <dd>{report.payments.toLocaleString(speechLocales[language])}</dd>
            </div>
            <div>
              <dt>{t('Refunds')}</dt>
              <dd>{money(report.refunds)}</dd>
            </div>
          </dl>
          <details>
            <summary>{t('View details')}</summary>
            <dl className="breakdown">
              {[
                ['UPI', report.upi],
                ['Cards', report.cards],
                ['Cash', report.cash],
              ].map(([label, amount]) => (
                <div key={label}>
                  <dt>{t(String(label))}</dt>
                  <dd>{money(Number(amount))}</dd>
                </div>
              ))}
            </dl>
            <p className="fine">
              {t('Sample data for the selected period. Net sales are total sales minus refunds.')}
            </p>
          </details>
        </div>
      )}
    </section>
  );
}
