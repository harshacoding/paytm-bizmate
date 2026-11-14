# BM-14 campaign review and BM-15 human handoff

Implemented together on `codex/bm-14-15-campaign-handoff`, from main `725f833`. This change supplies backend workflows and generated API contracts. BM-09 UI implementation is outside this branch.

## Start and exercise

Start or restart the backend to load this branch. From the repository root:

```sh
npm run dev
```

Swagger: http://127.0.0.1:8000/docs

In another terminal:

```sh
# Prepare and inspect an editable campaign without sending
python3 backend/scripts/smoke_review.py

# Edit, approve the exact new snapshot, send and verify delivery
python3 backend/scripts/smoke_review.py --edit-message 'Come back this week for 10% off' --approve

# Prepare a minimal handoff, approve it and verify its support reference
python3 backend/scripts/smoke_review.py --workflow handoff --approve

# Focused acceptance tests
uv run --project backend pytest backend/tests/test_campaign_handoff.py -q

# Complete project checks
npm run check
```

Campaign output shows 120 consenting inactive recipients, 24,000 paise estimated cost, and independently verified counts of 118 delivered and 2 failed. The result is simulated. Commercial outcome is explicitly `not_measured`.

Handoff output shows an approved support ticket with a verified `merchant_support` route, `ESCALATED` task status and `pending_human_support` for the requested change. The bank account is never changed by this application.

## BM-14 API flow

1. `POST /api/v1/tasks` with `{"message":"Send inactive customers message=\"Come back for 10% off\""}`.
2. `GET /api/v1/tasks/{task_id}/campaign` returns the editable message, inactivity window, audience, integer-paise cost, current approval, receipt, verification and delivery counts. Unprepared audience/cost values are null.
3. `PATCH /api/v1/tasks/{task_id}/campaign` with `{"expected_revision":COPY_CURRENT_REVISION,"message":"An exact edited offer"}`. Optional `inactivity_days` changes the eligibility window. Identity, recipient IDs, cost and approval decisions cannot be supplied here. A stale revision returns 409.
4. Edits cancel the old unexecuted approval through BM-06, preserve its original snapshot, refresh segmentation, and pause with a new pending approval and hash. No action is sent by editing. Previously approved inputs cannot be reused.
5. `POST /api/v1/tasks/{task_id}/approvals/{approval_id}` with `{"decision":"approve","input_hash":"COPY_CURRENT_HASH"}`. Cancellation uses `cancel`.
6. `POST /api/v1/tasks/{task_id}/resume`. Inspect `/campaign` again for independent delivery counts and evidence.

Eligibility and consent are checked at approval preparation, decision and immediately before execution. The provider checks the complete audience and cost again in the same SQLite transaction that writes the campaign. This catches revoked consent, recent orders and newly eligible customers. An audience change before execution cancels the old approval and prepares a new audience/cost snapshot for review. It does not silently send to a modified audience. The direct execute endpoint enforces the same precondition.

Completed, receipted and uncertain writes cannot be edited. A last-moment provider failure retains the uncertain execution for BM-08 inspection. It never authorizes another send. Independent verification failures retain the receipt and unresolved status. Existing BM-07/08 checkpoints and idempotency keys protect replay and restart. Each explicit review generation has a separate bounded read budget and fresh audience data, while previous attempts/results remain persisted.

## BM-15 API flow

1. `POST /api/v1/tasks` with `{"message":"Change my registered bank account"}`.
2. `GET /api/v1/tasks/{task_id}/handoff` returns the capability gap, plain-language explanation, minimal draft, support route and approval state. The draft uses trusted merchant context. It neither requests nor copies bank numbers, PINs, credentials, phone numbers or unrelated request text into the ticket.
3. Approve the exact saved support action using the same BM-06 approval endpoint, then call `/resume`.
4. The mock creates a support ticket. A separate `get_ticket_status` read must confirm both the reference and the `merchant_support` route. Only then is routing reported as verified and the `CapabilityGap.handoff_reference` populated. The requested change stays pending with human support.

Missing tools and denied permissions create persisted capability-gap telemetry. A handoff can be offered only when the current merchant has the independently required support permissions. Otherwise the task is escalated with an explanation and no invented approval, receipt or support reference. Permission-denied actions are never executed through a workaround. Cancellation creates no ticket. Uncertain support writes use BM-08 inspection; failed/missing routing evidence remains unverified. Public explanations and summaries support English, Telugu and Hindi.

Typed responses are available in OpenAPI and the generated frontend schema for Saiteja's BM-09/16 integration. Approval buttons, editable review forms and handoff cards remain UI work. Reviewer sign-off remains separate from implementation validation.

BM-17 backend integration and policy regression is added on this same branch. See the [repeatable evaluation and acceptance mapping](BM17_EVALUATION.md).

## Latest main integration

Main `960c108`, including BM-09/BM-16 and voice support, is merged into this branch. Its merchant UI is preserved and passes the existing 74 frontend tests alongside this backend. Approval/resume paths remain compatible. Managed campaign edits continue to use the BM-14 PATCH API until its UI control is connected. The API, rather than a local interface simulation, remains authoritative for refreshed audience, cost and approval snapshots.
