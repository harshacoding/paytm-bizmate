# BM 04 synthetic services

SQLite-backed providers implement payment records, settlement reports and credits, customers/orders/consent, support tickets and campaign delivery. Startup seeds two merchants once. Data, clock advancement and failure counters survive restart. Context, scopes and task ownership are enforced. Every record and action is synthetic.

The fixture produces sales of 2,000,000 paise, deductions of 24,000, 4,320, 80,000 and 35,000 paise, expected settlement of 1,856,680 paise and bank credit of 1,840,000 paise. A separate 16,680-paise credit becomes available after one synthetic day. The 200 customer histories contain 120 consent-eligible inactive recipients at 200 paise each, costing 24,000 paise. Separate campaign delivery reads report 118 delivered and 2 failed for this audience.

Run from the repository root and open http://127.0.0.1:8000/docs under **synthetic services**.

```sh
backend/.venv/bin/python -m uvicorn bizmate.main:app --host 127.0.0.1 --port 8000
```

API checks and demo controls

```sh
curl -sS http://127.0.0.1:8000/api/v1/demo/settlement
curl -sS http://127.0.0.1:8000/api/v1/demo/customers
curl -sS http://127.0.0.1:8000/api/v1/demo/clock
curl -sS -X POST http://127.0.0.1:8000/api/v1/demo/clock/advance -H 'Content-Type: application/json' -d '{"seconds":86400}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/demo/reset
curl -sS -X POST http://127.0.0.1:8000/api/v1/demo/failures -H 'Content-Type: application/json' -d '{"operation":"get_settlement_report","count":1}'
curl -i http://127.0.0.1:8000/api/v1/demo/settlement
curl -i http://127.0.0.1:8000/api/v1/demo/settlement
```

After failure injection, the first report read returns HTTP 503 with `MOCK_TIMEOUT` and the next succeeds. Additional scripts cover transaction/deduction/customer reads, fresh credits, ticket/delivery reads, and timeouts after committed ticket/campaign writes. The engine can inspect `lookup(context, action, idempotency_key)` before retrying an uncertain action.

CLI and database checks

```sh
backend/.venv/bin/python backend/scripts/demo_data.py seed
backend/.venv/bin/python backend/scripts/demo_data.py clock
backend/.venv/bin/python backend/scripts/demo_data.py advance --seconds 86400
backend/.venv/bin/python backend/scripts/demo_data.py reset --merchant merchant_demo
backend/.venv/bin/python backend/scripts/demo_data.py fail --operation ticket_after_write --count 1
backend/.venv/bin/python -m pytest backend/tests/test_mock_services.py -q
sqlite3 -header -column backend/.data/bizmate.sqlite3 'SELECT merchant_id, kind, COUNT(*) FROM mock_records GROUP BY merchant_id, kind;'
sqlite3 -header -column backend/.data/bizmate.sqlite3 'SELECT merchant_id, action, reference FROM mock_actions;'
```

`seed` preserves existing state. `reset` recreates only the selected merchant's mock data, actions, failures and clock. Business tasks and chat records keep their own lifecycle. Reads of provider references removed by a demo reset require unresolved-state handling by the workflow engine.

Set `BIZMATE_DEMO_CONTROLS_ENABLED=false` to reject reset, failure injection, consent changes and clock advancement through API and CLI. Database location follows `BIZMATE_DATABASE_PATH`. Local database files are excluded from Git.

Adapters implement the existing `services/ports.py` interfaces. `app.state.mock_services` supplies the providers and `app.state.tools` holds typed registrations. Ticket/send registry execution retains the BM-06 approval gate. Provider-level tests exercise writes directly and verify results through separate SQLite reads.

Campaign preparation stores `CampaignPayload` and returns the exact input hash. Sending requires that merchant/task-owned draft, revalidates consent inside the write transaction and persists the original inputs and receipt. Idempotency keys are scoped by merchant and action. Reuse with changed inputs raises `MockConflictError`. Concurrent retries reuse one receipt.

BM-12 scheduling, BM-13 business segmentation and BM-14 approval/send screens remain follow-on tasks. BM-04 supplies their stateful synthetic integration boundaries.
