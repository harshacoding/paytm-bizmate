# Paytm BizMate team ownership

**Team roster:** Harsha = Senior 1; Devi = Senior 2; Saiteja = Junior.

The team has two senior developers and one junior developer. You are Senior 1 and own the product's most consequential technical decisions: trusted identity, tool permissions, approvals, orchestration, recovery, reconciliation, and the settlement investigation. Senior 2 owns backend services, the remaining workflows, and integration testing. The junior owns the merchant interface, local setup, and demo packaging with senior review.

These are human team assignments. Each task has one accountable owner; support and review do not transfer that ownership. All acceptance criteria in [TASKS.md](TASKS.md) still apply.

## Responsibility summary

| Person | Primary responsibility | Owned tasks | Completion responsibility |
| --- | --- | --- | --- |
| **You / Senior 1** | Architecture, agent execution, trust controls, and settlement investigation | BM-02, BM-05, BM-06, BM-07, BM-08, BM-10, BM-11 | Prove the hero workflow can act only with permission and approval, recover safely, and explain the exact settlement gap. Review final integration and product behaviour. |
| **Senior 2** | Persistence, mock integrations, scheduled follow-up, win-back, handoff, and regression testing | BM-03, BM-04, BM-12, BM-13, BM-14, BM-15, BM-17 | Provide durable service contracts and independently verifiable mock outcomes; integrate all workflows and demonstrate restart safety. |
| **Junior** | App skeleton, chat/task interface, evidence views, setup documentation, and demo preparation | BM-01, BM-09, BM-16, BM-18 | Deliver usable merchant screens and a reproducible local demo. Implement approval interactions against backend contracts; backend authorization remains senior-owned. |

Task counts are not equal effort. Your seven tasks contain the highest-risk shared logic; Senior 2 has seven service/integration tasks; the junior's four tasks cover the application interface and packaging. Keep your time focused on the engine by letting Senior 2 handle routine backend integration and review the junior's changes.

## Detailed assignments and handoffs

| Task | Accountable owner | Reviewer | Required handoff |
| --- | --- | --- | --- |
| BM-01 Application skeleton | Junior | Senior 2 | Working frontend/backend startup and health check for both seniors. Senior 2 helps with dependency/configuration problems. |
| BM-02 Domain models and merchant context | You | Senior 2 | Versioned request/response models, lifecycle states, merchant-context rules, money types, and checkpoint identifiers. |
| BM-03 Storage and task APIs | Senior 2 | You | Durable repositories, task/timeline endpoints, and persistence interfaces consumed by your engine and the junior's UI. |
| BM-04 Synthetic data and mock services | Senior 2 | You | Stateful payment, ticket, CRM, and campaign adapters; ground-truth fixtures; repeatable reset and controlled clock. Junior may help author fixture data. |
| BM-05 Tool registry and permissions | You | Senior 2 | Registration/dispatch interface and metadata so Senior 2 can register adapters without modifying the policy core. |
| BM-06 Approvals, verification, idempotency | You | Senior 2 | Approval APIs, exact action snapshot, input hash, receipt/verification rules, and replay handling. Junior implements the review panel using this contract. |
| BM-07 Natural-language orchestration | You | Senior 2 | Structured intent and plan, graph execution, pause/resume, and task progress events. Senior 2 supplies storage/checkpoint integration. |
| BM-08 Failure recovery | You | Senior 2 | Retry and uncertain-outcome policies, error transitions, and recovery events. Senior 2 supplies scripted service failures. |
| BM-09 Chat and task workspace | Junior | Senior 2 | Reusable conversation, task list/detail, timeline, clarification, approval, loading, and error components. Use fixtures until APIs are ready. |
| BM-10 Reconciliation and proof card | You | Senior 2 | Deterministic calculation and source-linked proof response. Junior builds the proof-card component in the shared UI. |
| BM-11 Settlement investigation | You | Senior 2 | Integrated request-to-ticket workflow that stays open after ticket verification. Junior connects the settlement views; Senior 2 supplies ticket/report adapters. |
| BM-12 Scheduler and fresh-credit follow-up | Senior 2 | You | Persisted due-task runner and fresh-credit matching through your graph. Junior connects the demo time-control and pending/closed views. |
| BM-13 Segmentation and campaign cost | Senior 2 | You | Deterministic inactivity/consent result and cost estimate for the approved audience. |
| BM-14 Campaign execution | Senior 2 | You | End-to-end campaign flow using your approval/verification engine. Junior connects editable message, audience/cost review, and delivery result components. |
| BM-15 Capability-gap handoff | Senior 2 | You | Honest unsupported-request flow, confirmed support ticket, and pending human-owned status. Junior adds the limitation/handoff view. |
| BM-16 Evidence UI and UX | Junior | Senior 2 | Consistent responsive evidence, receipts, timestamps, pending/failure states, and synthetic-data labels across all workflows. You review the accuracy of claims and action wording. |
| BM-17 Workflow/policy regression | Senior 2 | You | Integrated regression suite and observed results. You write/maintain focused tests for your engine/policies; the junior checks browser flows and usability. |
| BM-18 Demo packaging | Junior | You | Setup/reset/test documentation, a timed script, and a recording/fallback. Senior 2 checks fresh-checkout setup; you rehearse and accept the complete demo. |

## Start together without blocking each other

### First shared checkpoint

Agree a thin first version of the BM-02 contracts before building deep implementations: Task/status, chat request, timeline event, settlement proof, approval request/decision, receipt, verification result, and merchant context. You own these definitions; Senior 2 checks persistence/API needs and the junior checks screen needs.

Then split the initial work:

- **You:** Lead BM-02, then start the BM-05 registry and BM-06 approval rules against agreed service interfaces.
- **Senior 2:** Help unblock backend setup, then implement BM-03 storage/APIs and BM-04 mock adapters against the shared models.
- **Junior:** Build BM-01 with Senior 2's support, then BM-09 with contract-shaped fixtures. Start with chat, task status, timeline, and a reusable approval panel.

Skeletons, fixture-based UI, and adapter stubs can be developed before every dependency is complete. A task is accepted only after its dependencies are integrated and its original acceptance criteria pass.

### Checkpoint 2: shared engine works

- You finish BM-05 to BM-08, including durable pause/resume and action-specific approval enforcement.
- Senior 2 proves task persistence, independent mock reads, and scripted failure injection.
- Junior connects the task workspace to real local APIs and verifies approve/cancel and clarification interactions.

Exit condition: a permitted mock action can pause for approval, resume once, produce a receipt, and pass a separate verification read after restart.

### Checkpoint 3: settlement journey works end to end

- You finish BM-10 and BM-11: exact Rs 166.80 reconciliation, evidence, recovery, approved ticket, independent ticket verification.
- Senior 2 finishes BM-12 using your graph: scheduled resume and fresh-credit verification.
- Junior connects proof, ticket, waiting state, time advancement, and verified closure.

Exit condition: the complete hero journey works from the merchant screen, survives restart, and closes only on fresh matching credit evidence.

### Checkpoint 4: remaining workflows work

- Senior 2 implements BM-13 to BM-15 using the existing registry and execution engine.
- You review consent enforcement, approved-input binding, completion rules, and unsupported-action handling; fix shared-engine gaps.
- Junior reuses existing cards/panels for campaign review and human handoff, then completes BM-16.

Exit condition: the campaign independently reports 118 delivered and 2 failed from 120 approved eligible recipients; bank-account change remains pending with support after a verified handoff.

### Checkpoint 5: repeatable demo

- Senior 2 leads BM-17 and integration fixes.
- You verify approval bypass, false completion, merchant isolation, uncertain write timeout, and fresh-evidence checks.
- Junior leads BM-18, browser checks, setup instructions, and recording; both seniors rehearse the demo.

Exit condition: all release checks in TASKS.md pass and a fresh checkout reproduces the three-minute demo.

## Ownership boundaries

These ownership boundaries now map to the runnable scaffold. See `docs/TEAM_START.md` and `docs/ARCHITECTURE.md` for existing files and unfinished implementation points.

| Owner | Primary code areas |
| --- | --- |
| You | Backend domain/session contracts, tool policy/registry, approval/verification engine, LangGraph orchestration/recovery, reconciliation, settlement workflow |
| Senior 2 | Database/repositories, task API transport, mock integrations/fixtures, scheduler, customer/campaign/handoff workflows, integration tests |
| Junior | Frontend components/screens/API client, project startup skeleton, demo documentation and recording |

- Keep shared contract definitions under your ownership. Senior 2 owns their database mappings and transport implementation. Agree changes before changing the contract or lifecycle semantics.
- Senior 2's workflow tools use your registry and approval engine. They must not add their own bypass path or independent completion rules.
- The junior implements display and user interactions; backend code decides whether an action is authorized, approved, executed, or verified. A disabled button is not an approval gate.
- Keep SQLite task state and LangGraph checkpoints coordinated through one agreed persistence interface, rather than competing implementations.
- Each owner supplies focused tests with their implementation. BM-17 combines these into the final regression run.
- Use task-sized branches such as `codex/bm-06-approval-engine`, `codex/bm-12-follow-up`, and `codex/bm-09-task-ui`. Merge the skeleton/contracts early, then small integrated changes. Assign one owner per shared file to reduce conflicting edits.
- You review changes to trust and completion rules and make the final integration call. Senior 2 handles routine service/UI reviews so every small change does not wait for you.

## Your immediate priorities

1. Publish the initial domain/API contracts with Senior 2 and the junior.
2. Implement the permission and approval core before consequential workflow actions.
3. Build the resumable orchestrator and bounded recovery.
4. Deliver deterministic settlement reconciliation and the investigation flow.
5. Review Senior 2's follow-up, campaign, and handoff integrations against the same guarantees.

Keep production authentication, real integrations, extra product features, and infrastructure expansion outside this MVP unless the team explicitly changes scope.
