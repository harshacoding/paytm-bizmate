import { useRef, useState } from 'react';
import { api } from '../api/client';
import type { LanguageCode, SettlementProof } from '../api/types';
import { errorText } from '../useWorkspace';
import { workspaceText } from '../workspaceText';
import { paise, stamp } from '../api/format';

const fields = [
  ['sales', 'Sales'],
  ['commission', 'Commission'],
  ['gst', 'GST'],
  ['refunds', 'Refunds'],
  ['chargeback', 'Chargebacks'],
  ['expected', 'Expected'],
  ['credit', 'Received'],
  ['residual', 'Still unexplained'],
] as const;

export function SettlementEvidence({
  language,
  allowed,
}: {
  language: LanguageCode;
  allowed: boolean;
}) {
  const [proof, setProof] = useState<SettlementProof | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const t = (text: string) => workspaceText(text, language);
  async function load() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      setProof(await api.reconcile());
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="api-evidence" aria-label={t('Settlement source check')}>
      <div className="api-section-heading">
        <h3>{t('Settlement source check')}</h3>
        <button className="secondary" disabled={!allowed || busy} onClick={() => void load()}>
          {t(busy ? 'Checking' : 'Check source records')}
        </button>
      </div>
      <p className="api-disclaimer">
        {t(
          'This reads synthetic source records. It does not execute an action or complete the task.',
        )}
      </p>
      {error && <p role="alert">{error}</p>}
      {proof && (
        <>
          <span className="api-status">
            {t(
              proof.status === 'complete'
                ? 'Source comparison ready'
                : proof.status === 'conflicting'
                  ? 'Conflicting source records'
                  : 'Some source records are missing',
            )}
          </span>
          <small>
            {t('Captured')} · {stamp(proof.captured_at, language)}
          </small>
          <div className="api-proof-grid">
            {fields.map(([field, label]) => {
              const line = proof[field];
              return (
                <article className="api-proof" key={field}>
                  <h4>{t(label)}</h4>
                  <strong>
                    {line.amount_paise === null ? t('Unknown') : paise(line.amount_paise, language)}
                  </strong>
                  <details>
                    <summary>{t('View details')}</summary>
                    <p>{line.explanation}</p>
                    {line.source_references.map((reference) => (
                      <code key={reference}>
                        {reference}
                        <br />
                      </code>
                    ))}
                  </details>
                </article>
              );
            })}
          </div>
          {proof.warnings.map((warning) => (
            <p className="api-warning" key={warning}>
              {warning}
            </p>
          ))}
          <p className="api-disclaimer">
            {t('A source comparison is not proof that an unresolved credit has arrived.')}
          </p>
        </>
      )}
    </section>
  );
}
