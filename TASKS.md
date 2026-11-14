# Paytm BizMate build tasks

This backlog turns the complete PRD v1.0 into implementation tasks for the hackathon MVP. The first deliverable is a working settlement investigation from natural-language request through verified follow-up. Customer win-back and capability-gap handoff then reuse the same task engine.

All tasks below are required for the MVP. A runnable initial scaffold is provided; durable storage, workflow execution and the remaining acceptance criteria still need implementation. Check a task only after its acceptance criteria pass and the assigned reviewer accepts it.

The three-person ownership split and handoffs are in [TEAM_PLAN.md](TEAM_PLAN.md). Harsha owns the core agent, permissions, approval/recovery engine, reconciliation, and settlement investigation; Devi owns services and remaining workflows; Saiteja owns the interface and demo packaging.

## Scope and implementation decisions

- Follow `Paytm_BizMate_Complete_PRD.docx` as the product specification. PRD section numbers below provide traceability.
- Use React and TypeScript for the merchant interface; Python and FastAPI for the backend; one LangGraph orchestrator; SQLite and durable LangGraph checkpoints for persistence.
- Use synthetic merchant data and mock support, settlement, CRM, and campaign services. Every simulated result must be labelled.
- Derive merchant identity from a trusted server-side demo session. The demo session is not production authentication. Never accept an LLM-selected merchant identity.
- Calculate money in integer paise. The LLM interprets intent, proposes plans, and explains recorded evidence; deterministic code calculates amounts and validates actions.
- Require action-specific approval before consequential actions. A successful write is followed by a separate verification read.
- Keep voice, live payment/bank integrations, real marketing sends, inventory, forecasting, billing, and a general-purpose multi-agent platform outside this build.

## Milestones

| Milestone | Result | Tasks |
| --- | --- | --- |
| M1 Foundation | Local app, scoped data, mock services, durable task records | BM-01 to BM-04 |
| M2 Task engine | Validated plans, permissions, approvals, recovery, progress UI | BM-05 to BM-09 |
| M3 Settlement | Explain the gap, verify a support ticket, resume and verify the credit | BM-10 to BM-12 |
| M4 Remaining workflows | Approved simulated win-back and honest support handoff | BM-13 to BM-15 |
| M5 Demonstrable MVP | Complete evidence UI, regression checks, repeatable demo | BM-16 to BM-18 |

## M1 Foundation

### BM-01 Create the application skeleton

- [ ] Complete
- **Scaffold status:** Initial setup supplied; Saiteja and Devi should review and extend it using `docs/TEAM_START.md`.
- **Owner:** Saiteja
- **Reviewer:** Devi
- **Depends on:** none
- **PRD:** 9.1, 13
- **Deliver:** `frontend/`, `backend/`, development configuration, `.env.example`, health endpoint, and initial setup instructions. Pin actual package versions during implementation.
- **Acceptance:** A fresh checkout can start the frontend and backend using documented commands. The frontend reaches the health endpoint. Secrets, local databases, and build output are excluded from Git. Model credentials are used only on the backend.

### BM-02 Define domain models and trusted merchant context

- [ ] Complete
- **Implementation status:** Implemented on `codex/bm-02-domain-context`; validation and merchant-isolation tests added. Awaiting Devi's review. See `docs/BM_02_CONTRACTS.md`.
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-01
- **PRD:** 9.6, 10, 11, 12
- **Deliver:** Validated backend models and matching frontend contracts for Merchant, Conversation, Message, LanguageContext, Task, PlanStep, ToolExecution, Approval, Receipt, Evidence, Verification, and CapabilityGap; conversation/task relationships; explicit lifecycle transitions; a server-resolved synthetic merchant session.
- **Build:**
  - Define shared Conversation, Message and LanguageContext models.
  - Add preferred_language to merchant and conversation contracts.
  - Add detected_language and response_language metadata to message contracts.
  - Support language codes en, te and hi.
  - Associate tasks with an optional conversation_id.
  - Preserve original message content, including whitespace and Unicode.
- **Acceptance:** Tools and task APIs enforce the current merchant's scopes and ownership. A second synthetic merchant cannot read, approve, or execute another merchant's task. An identity supplied in a message or tool argument cannot override the session. Monetary fields use integer paise.

### BM-03 Add durable storage and task APIs

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-02
- **PRD:** 9.6, 10, 12, 13
- **Deliver:** SQLite schema and initialization, repositories, task list/detail endpoints, readable event timeline, approval records, evidence records, and an agreed polling or event-stream contract. Establish the relationship between task IDs and LangGraph checkpoint IDs.
- **Acceptance:** Tasks, approvals, receipts, retry history, next action, and next run time survive a backend restart. Task status and timeline are merchant-scoped and ordered consistently. APIs return stable identifiers and validation errors.

### BM-04 Seed synthetic data and stateful mock services

- [x] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-02
- **PRD:** 7, 9.5, 14, 20
- **Deliver:** Seed/reset utilities and mock records for transactions, deductions, settlement reports and bank credits, customers/orders/consent, tickets, and campaigns. Include a second merchant for isolation checks, scripted failures, and a controlled demo clock.
- **Acceptance:** Fixtures reproduce the settlement and campaign figures below. A reset recreates the same demo state. Mock writes persist references which separate read tools can inspect; verification is not just an echo of the write response. Failure injection and clock controls are available only in demo mode.

## M2 Task engine

### BM-05 Implement the typed tool registry and permission checks

- [ ] Complete
- **Implementation status:** Registry, policy tests and BM-04 adapter registration implemented on `codex/bm-05-tool-registry`. Rebased onto main including BM-04; BM-07 planner integration and Devi's review remain pending. See `docs/BM_05_TOOL_REGISTRY.md`. Side effects remain blocked until BM-06.
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-02, BM-04
- **PRD:** 8, 9.2, 9.4, 9.5, 11
- **Deliver:** Tool registration, relevant-tool discovery, validated dispatch, required scopes, risk labels, preconditions, handler references, approval requirements, idempotency behaviour, and verification specifications.
- **Acceptance:** Unknown tools, malformed inputs, missing scopes, and failed preconditions are rejected by backend code. The planner sees only relevant permitted tools. No bank-account-change or real payment tool is registered.

### BM-06 Implement approvals, receipts, verification, and idempotency

- [ ] Complete
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-03, BM-05
- **PRD:** 4.2, 9.2, 10, 10.1, 11, 12
- **Deliver:** Approval request/approve/cancel APIs, immutable action input snapshots and hashes, execution-time validation, durable idempotency keys, receipt storage, and independent verification records.
- **Acceptance:** Missing, cancelled, wrong-merchant, or mismatched approvals cannot authorize execution. Editing an approved action's inputs requires new approval. Replaying an execution does not create duplicate tickets or sends. A write receipt alone cannot complete a task. Verification failure leaves a visible unresolved state.

### BM-07 Build natural-language intake and the LangGraph orchestrator

- [ ] Complete
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-03, BM-05, BM-06
- **PRD:** 6, 9.2, 9.3, 9.6, 10
- **Deliver:** Structured intent/goal extraction, concise clarification, tool-based plans, backend plan validation, step execution, durable checkpoints, and pause/resume for input and approval. Centralize model configuration and prompts.
- **Acceptance:** Natural wording starts each supported workflow. Ambiguous consequential requests pause for clarification. Invalid model output cannot bypass validation or invoke arbitrary tools. Restarting resumes the saved task without repeating a completed side effect. Tool and document content is treated as data and cannot grant permissions or approval.

### BM-08 Add bounded recovery and uncertain-outcome handling

- [ ] Complete
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-04, BM-06, BM-07
- **PRD:** 7.1, 10.1, 13, 19
- **Deliver:** Configured retry limits for safe reads, explicit failure events, checkpoint-before-pause, fallback selection, and inspection of side-effect state before any retry after an uncertain timeout.
- **Acceptance:** A scripted report timeout exhausts only bounded safe retries and records the fallback. A timeout after a ticket/send was actually recorded does not cause a duplicate. Incomplete or conflicting evidence cannot produce a confident financial explanation or false completion. Unsafe recovery escalates with a reason and saved state.

### BM-09 Build the chat and task workspace

- [ ] Complete
- **Owner:** Saiteja
- **Reviewer:** Devi
- **Depends on:** BM-01, BM-02, BM-03; integrate with BM-07
- **PRD:** 6, 13, 14
- **Deliver:** Merchant context, example prompts, conversation composer, task list, status/progress, next action, timeline, clarification inputs, approval/cancel controls, and loading/error states.
- **Acceptance:** The merchant can start work in everyday language, leave and reopen a task, answer a question, and approve or cancel an exact action. Pending and failed work remains visible. Raw tool payloads are hidden by default. Synthetic/demo labels are clearly visible.

## M3 Settlement investigation

### BM-10 Implement reconciliation and the source-linked proof card

- [ ] Complete
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-04, BM-05; UI uses BM-09
- **PRD:** 7.1, 12.1, 14
- **Deliver:** Transaction/report/deduction reads, deterministic reconciliation, source references, and a proof card showing each component and the unexplained amount.
- **Acceptance:** Seeded sales of 2,000,000 paise less commission 24,000, GST 4,320, refunds 80,000, and chargeback 35,000 produce expected settlement of 1,856,680 paise. Against bank credit of 1,840,000 paise, the residual is exactly 16,680 paise (Rs 166.80). Each displayed amount links to its source. Missing records remain explicit unknowns rather than zero-valued assumptions.

### BM-11 Complete investigation and approved support-ticket creation

- [ ] Complete
- **Owner:** Harsha
- **Reviewer:** Devi
- **Depends on:** BM-06, BM-07, BM-08, BM-09, BM-10
- **PRD:** 6.2, 7.1
- **Deliver:** The merchant-facing settlement flow: request, plan, retrieval/recovery, explanation, draft case, explicit ticket approval, mock creation, receipt, separate ticket-status read, and a pending next action.
- **Acceptance:** The scripted timeout is visible and handled safely. The merchant sees the Rs 166.80 residual and case evidence before approving. The ticket reference is independently verified. Verifying ticket creation does not close the settlement investigation; the unresolved credit leaves it waiting for follow-up.

### BM-12 Add scheduled follow-up and fresh-credit verification

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-03, BM-04, BM-07, BM-11
- **PRD:** 7.1, 9.6, 10, 14, 15
- **Deliver:** Persisted `next_run_at`, due-task runner, controlled advance-time UI, resumed settlement checks, a synthetic proactive mismatch alert, and fresh-credit verification.
- **Acceptance:** A due task resumes after process restart. Only a new settlement record that matches the merchant and outstanding amount can resolve the Rs 166.80 gap. Reusing old evidence cannot close it. A missing or conflicting credit keeps the task open or escalates. Re-running the scheduler does not duplicate tickets or closure events. Time advancement is explicitly a demo control.

## M4 Customer win-back and capability-gap handoff

### BM-13 Implement consent-aware customer segmentation and cost calculation

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-04, BM-05
- **PRD:** 7.2, 11, 12.1
- **Deliver:** Customer/order read, inactivity-window handling, deterministic segmentation, consent filtering, and deterministic illustrative cost calculation.
- **Acceptance:** Use 30 days when the merchant does not specify a window; the exact 30-day boundary is handled consistently with the controlled clock. The primary fixture analyses 200 histories and returns 120 eligible inactive customers at Rs 2 each, totaling Rs 240. Additional fixtures prove that non-consenting customers and other merchants' customers are excluded.

### BM-14 Build campaign review, approval, simulated send, and delivery verification

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-06, BM-07, BM-08, BM-09, BM-13
- **PRD:** 6.3, 7.2, 14
- **Deliver:** Editable campaign draft, eligible audience summary, cost estimate, exact-input approval, idempotent mock send, receipt, and independent delivery-status read.
- **Acceptance:** The merchant can edit the message before approval. Approval binds the exact message, recipient set, and cost; changed inputs require new approval. Eligibility and consent are revalidated at execution; a changed audience requires review. The seeded status read reports 118 delivered and 2 failed. The result is clearly simulated, failed deliveries remain visible, and no repeat visits or revenue uplift is claimed.

### BM-15 Implement capability-gap detection and confirmed human handoff

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-05, BM-06, BM-07, BM-09
- **PRD:** 7.3, 11, 14
- **Deliver:** Missing-capability/permission handling, plain-language limitation, minimal-information handoff draft, approval, mock support routing, independent reference verification, and CapabilityGap telemetry.
- **Acceptance:** “Change my registered bank account” cannot invoke an account-change tool or workaround. The merchant approves the handoff before a ticket is created. A separate read verifies the support reference. The request remains pending with human support, with an escalated status where appropriate; the UI never claims the bank account was changed. Permission-denied requests receive the same honest boundary handling.

## M5 Verification and demo readiness

### BM-16 Finish evidence views and merchant-facing UX

- [ ] Complete
- **Owner:** Saiteja
- **Reviewer:** Devi
- **Depends on:** BM-09, BM-11, BM-12, BM-14, BM-15
- **PRD:** 6.4, 13, 14
- **Deliver:** Readable receipts and verification timestamps, support handoff panel, unresolved-item summaries, responsive layouts, accessible controls, and consistent wording for all states.
- **Acceptance:** A merchant can distinguish approved, executed, independently verified, pending, failed, and escalated work. Proof cards, campaign review, and approval panels show relevant consequences. Cancelling or deferring approval is supported. Screens do not expose secrets, unnecessary customer details, or implementation jargon. Error and empty states explain the next step.

### BM-17 Run meaningful workflow and policy regression checks

- [ ] Complete
- **Owner:** Devi
- **Reviewer:** Harsha
- **Depends on:** BM-08, BM-12, BM-14, BM-15, BM-16
- **PRD:** 4.2, 7 acceptance criteria, 10.1, 11, 16, 19, 22
- **Deliver:** Repeatable tests and an evaluation summary covering exact arithmetic, consent, merchant isolation, approvals, verification, idempotency, restart recovery, and unsupported work. Add focused tests alongside the earlier tasks rather than postponing all testing to this task.
- **Acceptance:** Tests cover no approval, cancelled approval, changed inputs, cross-merchant access, missing consent, a 30-day boundary, read timeout, uncertain write timeout, repeated execution, independent verification failure, and stale settlement evidence. Restart tests exercise actual persisted state. Target zero approval bypasses and zero false completions. Report observed results and failures without inventing performance or commercial gains.

### BM-18 Package and rehearse the repeatable three-minute demo

- [ ] Complete
- **Owner:** Saiteja
- **Reviewer:** Harsha
- **Depends on:** BM-12, BM-14, BM-15, BM-16, BM-17
- **PRD:** 13, 15, 16, 20, 22
- **Deliver:** Updated README with setup/model configuration, seed/reset instructions, start commands, test commands, known limitations, and a timed demo script; capture a short successful run or deterministic fallback.
- **Acceptance:** A fresh checkout can reproduce: proactive alert; report timeout and Rs 166.80 proof; approved and verified ticket; persisted scheduled follow-up and verified closure; 120-recipient/Rs 240 campaign with 118 delivered and 2 failed; unsupported bank change and verified pending handoff. The demo fits roughly three minutes, labels mocks, and shows actual test results. Reset removes prior demo side effects without affecting another environment.

## Suggested build order

1. Complete BM-01 to BM-04 and agree the typed contracts.
2. Complete BM-05 to BM-08 while building the BM-09 interface against those contracts.
3. Complete BM-10 to BM-12 as the first fully working product journey. Verify restart and follow-up before expanding.
4. Complete BM-13 and BM-14, then BM-15, reusing the same approval, execution, and verification engine.
5. Complete BM-16 to BM-18 and fix any failed acceptance criteria before calling the MVP done.

Work that can proceed independently once its dependencies exist: interface layout, deterministic reconciliation, customer segmentation, and fixture authoring. They must share the same contracts and fixtures. Approval enforcement, checkpoint behaviour, and completion rules are shared backend responsibilities.

## Release checks

- [ ] All 18 tasks pass their acceptance criteria.
- [ ] Both product workflows start with natural-language requests.
- [ ] Permission checks and action-specific approvals cannot be bypassed.
- [ ] Settlement arithmetic matches the seeded truth to the paise.
- [ ] An independent read verifies every consequential mock action.
- [ ] Tasks and approvals survive restart; scheduled work resumes safely.
- [ ] Only fresh matching credit evidence closes the settlement investigation.
- [ ] Only approved, consent-eligible recipients enter the simulated campaign.
- [ ] Bank-account change remains pending with human support.
- [ ] UI, demo, and documentation make synthetic and simulated boundaries clear.
- [ ] Clean local setup, seed/reset, test run, and complete demo have been exercised.
