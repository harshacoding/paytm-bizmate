# Settlement investigation and follow-up

BM-11 and BM-12 are implemented together as a deterministic backend workflow. It reuses BM-10 proof calculation, BM-04 synthetic providers and BM-06 exact-input approval. No new dependencies or database migrations are required.

The merged BM-07/BM-08 natural-language graph now saves the settlement baseline and connects its verified-ticket step to this follow-up worker. POST `/api/v1/tasks` and its normal approval/resume flow work with the same fresh-credit completion guard. English, Telugu and Hindi response context survives follow-up and closure. The explicit settlement APIs below also work independently. The merchant task screen supports workflow continuation and due checks. Demo planning is deterministic unless the backend Sarvam or OpenAI planner is configured.

## UI/API handoff

| Method | Route | Response |
| --- | --- | --- |
| POST | `/api/v1/settlements/investigations` | 201 `InvestigationView` |
| GET | `/api/v1/settlements/investigations/{task_id}` | `InvestigationView` |
| POST | `/api/v1/settlements/investigations/{task_id}/resume` | `InvestigationView` |
| POST | `/api/v1/settlements/scan` | List of proactive mismatch investigations |
| POST | `/api/v1/settlements/run-due` | List of tasks changed by this scoped due pass |

`InvestigationView` contains `task`, typed `state`, and optional `resolution`. State includes the source-linked `proof`, exact `case_summary`, approval/ticket references and retry counters. Existing task/timeline endpoints remain available. Unknown or other-merchant investigations return 404; permissions return 403; conflicting state/request IDs return 409; invalid request shape returns 422.

Start with a stable client request ID:

```json
{
  "client_request_id": "settlement-ui-1",
  "settlement_reference": "settlement-001",
  "message": "Why is my settlement short?",
  "conversation_id": null
}
```

Only `client_request_id` is required. Retrying the same ID and payload returns the existing investigation, still HTTP 201; changed payload with that ID returns 409. Original message content is preserved. A supplied conversation must belong to the resolved merchant. Identity, permissions and task status cannot be supplied in the body.

The backend retrieves and saves the proof and support draft, then returns `AWAITING_APPROVAL`. The UI must display the residual, evidence and exact draft before approval. Approve/cancel through the existing BM-06 endpoint using the returned approval ID and hash:

```text
POST /api/v1/tasks/{task_id}/approvals/{approval_id}
{"decision":"approve","input_hash":"<server-returned-hash>"}
```

Then POST the investigation's `/resume` endpoint with no body (graph-backed tasks are routed to their durable orchestrator). This executes the approved snapshot once, independently verifies ticket status and schedules follow-up. Deferring approval sends nothing; cancellation leaves the task in PLANNING for future replanning. Resume never revives cancelled approval or retries an uncertain ticket write. A failed ticket-status read may be retried by resuming; it reads the saved ticket rather than creating another.

## Investigation rules

- The report read has at most three attempts, persisted before each call. Timeout events show attempt numbers. Exhaustion records a visible fallback to available transaction, deduction and bank-credit ledger sources. Unavailable fallback or incomplete/conflicting evidence escalates without inventing amounts or creating a case.
- Seeded expected settlement is 1,856,680 paise against 1,840,000 credited, leaving 16,680 paise (Rs 166.80). The entire BM-10 source-linked proof is saved; the support draft refers to that proof.
- No positive unexplained shortfall means no support action: the task asks for clarification. A scan with incomplete/conflicting evidence returns a conflict rather than claiming everything is clear.
- The support action always goes through BM-06. Missing/cancelled/mismatched approval cannot send it. A write timeout remains visibly unresolved with no follow-up due time; BM-08 must inspect/reconcile that claim before proceeding.
- Ticket verification is separate from settlement resolution. A verified support reference moves the task to WAITING_EXTERNAL, not COMPLETED.

## Follow-up and clocks

The saved task has `schedule_clock: "demo"`. Its `next_run_at` is measured against the current merchant's controlled demo clock, initially one demo day after ticket verification. Other tasks default to `schedule_clock: "system"`. Creation/update/audit timestamps remain server timestamps; the UI must label a demo due time accordingly instead of comparing it with browser wall time.

The backend checks due work at startup and every five seconds for its server-configured merchant. Shutdown waits for an in-flight pass. Manual `/run-due` performs the same scoped check. The existing demo clock-advance endpoint also runs due work after advancing, so this command drives the seeded follow-up:

```text
POST /api/v1/demo/clock/advance
{"seconds":86400}
```

Advancing time remains a demo-only control. This does not send another ticket. A backend restart resumes saved waiting tasks. A durable 30-second server-time lease protects an active check; an interrupted read can resume after that lease expires. Attempt tokens are saved with the claim, so restarts cannot reset the three-check limit. Competing processes use repository revisions to prevent duplicate closure.

Every follow-up confirms the baseline sources are unchanged and reads newly available records scoped to the merchant. Closure requires exactly one fresh credit for the same settlement, a new source reference, availability after the baseline proof was captured, and an amount exactly equal to the outstanding residual. The current full settlement must also reconcile to zero. Stale, wrong-settlement or other-merchant credits do not resolve it; changed baselines, conflicting amounts or multiple candidates escalate. Missing credit/read timeouts reschedule by one demo day, up to three attempts before escalation.

The fresh payment is attached as Evidence and a typed `SettlementResolution` is saved separately from ticket Verification. Completion checks require both verified receipts and fresh-credit resolution; a ticket receipt/read alone cannot close a settlement. Successful closure clears the due time, finishes plan steps and emits one closure event. A restart between saving resolution and recording completion resumes finalization without duplicating evidence or the closure event.

## Proactive alert

POST `/scan` detects the synthetic mismatch without a merchant-authored request and creates a pending investigation. Repeated scans reuse the existing investigation for that merchant/settlement. It never approves or sends the support case. This is an explicit backend/demo scan trigger for the UI; it does not send notifications or install a global multi-merchant cron job. Do not describe an empty scan result as a completed settlement workflow.

## Checks and remaining integration

Run `npm run check`. Focused coverage is in `backend/tests/test_settlement_investigation.py`: full approval-to-credit journey, bounded retries/fallback, cancellation and uncertain writes, failed ticket verification, request/scan deduplication, evidence rejection, restart at startup and between checkpoints, durable leases/retry budgets, concurrent runners and merchant isolation.

BM-07 now attaches typed investigation state during preparation and schedules follow-up after independent ticket verification. It retains its graph checkpoints, bounded read recovery and inspection-only uncertain-write recovery. Saiteja can build against the explicit APIs and generated OpenAPI/TypeScript types now. Production scheduling/authentication remain outside this PR. The explicit deterministic `/investigations` flow leaves uncertain writes for inspection; graph-backed tasks reuse BM-08 inspection recovery.


## Merchant UI integration after rebase

The connected task screen now routes explicit investigation execution/continuation through the settlement workflow endpoint; graph-backed tasks retain normal orchestration resume. Exact approval is still a separate merchant decision. The UI never directly executes or verifies an investigation action outside that workflow.

Scheduled demo tasks show **Scheduled time (demo clock)** and explain that browser wall time does not drive the schedule. **Check due follow-ups** invokes the scoped due pass once, then refreshes authoritative task status, evidence and events. It does not advance time, approve an action, repeat a support ticket or claim credit arrived. Tasks without payment-read/write permissions cannot invoke the check. Existing polling displays backend-verified closure; no local timer completes a goal. The controlled clock-advance API remains the explicit demo tool documented above.

UI regression coverage includes English/Telugu/Hindi due labels, click deduplication, permissions, exact approval before workflow continuation and absence of competing execute/verify calls. The supplied READY fixtures now include the shared `schedule_clock` field. Final reviewer and full-demo acceptance remain pending.
