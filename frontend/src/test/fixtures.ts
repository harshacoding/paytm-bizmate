import type { DemoPreview, Session, Task } from '../api/types';

export const session: Session = {
  mode: 'synthetic_local_demo',
  merchant: { merchant_id: 'merchant_demo', display_name: 'Sharma General Store', scopes: [] },
};
export const task: Task = {
  task_id: 'task-one',
  revision: 1,
  conversation_id: null,
  merchant_id: 'merchant_demo',
  goal: 'Investigate a short settlement',
  original_request: 'Why is my settlement short?',
  intent: 'unknown',
  status: 'AWAITING_INPUT',
  plan: [],
  evidence: [],
  approvals: [],
  receipts: [],
  verifications: [],
  executions: [],
  workflow_data: {},
  next_action: 'Workflow execution is not implemented (BM-07).',
  next_run_at: null,
  checkpoint_id: null,
  events: [
    {
      event_id: 'e',
      kind: 'scaffold_pending',
      message: 'No investigation has run.',
      occurred_at: '2026-11-14T04:00:00Z',
    },
  ],
  created_at: '2026-11-14T04:00:00Z',
  updated_at: '2026-11-14T04:00:00Z',
  simulated: true,
};
export const preview: DemoPreview = {
  simulated: true,
  description: 'Static synthetic preview only. No investigation or campaign has run.',
  settlement: {
    sales_paise: 2000000,
    commission_paise: 24000,
    gst_paise: 4320,
    refunds_paise: 80000,
    chargeback_paise: 35000,
    expected_paise: 1856680,
    credit_paise: 1840000,
    residual_paise: 16680,
    source_references: ['fixture:credit-001'],
  },
  campaign: {
    histories_count: 200,
    inactivity_days: 30,
    eligible_count: 120,
    estimated_cost_paise: 24000,
    delivered_count: 118,
    failed_count: 2,
  },
};
