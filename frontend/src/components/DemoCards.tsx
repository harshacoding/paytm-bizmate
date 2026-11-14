import type { DemoPreview } from '../api/types';

export const rupees = (paise: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(paise / 100);

export function DemoCards({ preview }: { preview: DemoPreview }) {
  const p = preview.settlement;
  const rows: [string, number][] = [
    ['Sales', p.sales_paise],
    ['Commission', -p.commission_paise],
    ['GST on commission', -p.gst_paise],
    ['Refunds', -p.refunds_paise],
    ['Chargeback', -p.chargeback_paise],
  ];
  return (
    <section className="preview-area" aria-label="Synthetic component previews">
      <div className="section-title">
        <div>
          <span className="eyebrow">BUILDING BLOCKS</span>
          <h2>A look at what’s next</h2>
        </div>
        <span className="badge subtle">Static preview</span>
      </div>
      <p className="muted preview-caption">
        {preview.description} These values are separate from your selected task.
      </p>
      <div className="preview-grid">
        <article className="card proof-card">
          <span className="card-icon">₹</span>
          <h3>Understand a settlement</h3>
          <p className="muted">Every amount, with a source.</p>
          <dl className="ledger">
            {rows.map(([label, amount]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{rupees(amount)}</dd>
              </div>
            ))}
            <div className="ledger-total">
              <dt>Expected</dt>
              <dd>{rupees(p.expected_paise)}</dd>
            </div>
            <div>
              <dt>Bank credit</dt>
              <dd>{rupees(p.credit_paise)}</dd>
            </div>
          </dl>
          <div className="residual">
            <span>Unexplained balance</span>
            <strong>{rupees(p.residual_paise)}</strong>
          </div>
          <details>
            <summary>Fixture source references</summary>
            <ul>
              {p.source_references.map((ref) => (
                <li key={ref}>{ref}</li>
              ))}
            </ul>
          </details>
        </article>
        <article className="card campaign-card">
          <span className="card-icon">↗</span>
          <h3>Bring customers back</h3>
          <p className="muted">A consent-first campaign preview.</p>
          <div className="audience">
            <strong>{preview.campaign.eligible_count}</strong>
            <span>eligible recipients in the sample</span>
          </div>
          <div className="campaign-facts">
            <span>{preview.campaign.inactivity_days}+ days inactive</span>
            <span>{rupees(preview.campaign.estimated_cost_paise)} estimated</span>
          </div>
          <label htmlFor="offer">Sample offer · editable preview</label>
          <textarea
            id="offer"
            defaultValue="We’ve missed you! Visit this week to discover our latest offers."
            rows={3}
          />
          <button className="button disabled" disabled>
            Review & send · coming in BM-14
          </button>
          <p className="fineprint">
            No message will be sent. Consent checks, approval and delivery verification are not
            implemented yet.
          </p>
        </article>
      </div>
    </section>
  );
}
