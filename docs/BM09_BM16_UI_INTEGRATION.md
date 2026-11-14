# BM-09 and BM-16: connected merchant workspace

Owner: Saiteja. Reviewer: Devi. Frontend implementation ready for review.

## Contract and source

The supplied `Paytm_BizMate_UI_API_Contract.zip` describes backend commit
`de8ff05ed3d6ffc710e78d6d0b3d40b4250e679a` (BM-02/03/04/05/06/13).
This branch integrates `origin/main` through `8cbe069`, including BM-10's
source-linked settlement reconciliation, and preserves the backend voice proxy.
The checked-in OpenAPI and TypeScript definitions are generated from this combined
backend. The two READY task fixtures in `frontend/src/test/contract-fixtures/`
are copied unchanged from the supplied packet. They are response snapshots,
not task creation payloads.

## Merchant experience

- `/` is the connected workspace. It requires the API; unavailable services show
  an error and retry, never invented records.
- Session identity and scopes come from the server. New/reopened conversations,
  original messages and task snapshots are loaded through scoped APIs.
- A submitted chat uses one stable `client_message_id`. The merchant can retry
  the same uncertain turn without changing its content or creating a second ID.
  Pending turns survive a page reload in session storage, scoped by merchant.
- Sending a chat does **not** also create a task. Each user message has an explicit
  “Start a task from this question” action. The contract's intake currently returns
  AWAITING_INPUT. The UI displays that state and the server's next action.
- “Your tasks” shows this conversation's tasks, with an “All tasks” view for
  older/unlinked work. Details include lifecycle status, next action, plan progress,
  clarification, timeline, approvals, execution receipts, verification and handoffs.
- Task details poll every two seconds while visible. Background polling pauses
  when hidden; stale selections and lower revisions cannot overwrite current work.
- Language selection PATCHes the conversation's fallback preference. Original
  history is never translated or rewritten. Message `response_language` determines
  assistant content language and the associated task interface language where
  available. The current backend scaffold replies in English until BM-07 implements
  detection and generation; the UI does not pretend otherwise.
- Numeric unread badges count unread assistant messages and clear when the
  conversation is opened. Browser read markers contain sequences, not message text.
- The existing animated, timed walkthrough remains at `/?demo=1`, labelled as
  sample data/simulated actions. Its locally simulated outcomes are not server
  receipts or financial evidence.

## Exact approvals and evidence

1. A backend-prepared READY task can request a support or campaign approval.
   The browser never manufactures READY status, changes a plan or sets completion.
2. Campaign audience and integer-paise cost come from the segmentation endpoint.
   The merchant edits the offer before requesting its approval snapshot.
3. Review shows the server's exact saved summary/offer, recipient count and cost.
   Approval uses the returned `input_hash`. Cancel records a decision; “Decide later”
   leaves approval pending without a mutation. Editors do not overwrite snapshots.
4. Execution is a separate explicit action and submits `approved_inputs` exactly.
   Duplicate clicks are locked. Network/conflict errors reconcile Task first;
   uncertain claims never trigger an automatic resend.
5. Receipts prove execution only. Independent verification is bodyless POST, and
   HTTP 200 with `verified=false` visibly remains failed/unresolved. The latest
   verification per receipt is shown with its timestamp. Only backend COMPLETED
   is displayed as goal completion.
6. Financial evidence shows original descriptions, exact paise, capture times and
   source references behind “View details”. A separate BM-10 source check shows
   sales, each deduction, expected settlement, received credit and unexplained
   residual. Missing/conflicting amounts stay unknown rather than becoming zero.
7. Handoff panels show capability gaps, ticket references and pending support.
   A verified ticket never implies the missing settlement arrived or a bank
   account changed.

## Run and review

From the repository root:

```sh
npm ci
uv sync --project backend --locked --extra dev
npm run dev
```

Open `http://127.0.0.1:5173`. Create a conversation, submit a question, reload,
switch conversations, start an explicit task and save a clarification. Change the
language selector and confirm earlier assistant messages remain in their original
language.

New chat/intake does not yet generate an executable plan. To review approval
screens against real endpoints, prepare a **dedicated local database** explicitly:

```powershell
uv run --project backend python backend/scripts/seed_ui_review.py --database backend/.data/ui-review.sqlite3
$env:BIZMATE_DATABASE_PATH = '.data/ui-review.sqlite3'
npm run dev:api
```

Run the frontend separately with `npm run dev:web`. Under “Your tasks”, select
“All tasks”; the packet supplies `ui-ticket-fixture` and `ui-campaign-fixture`.
They are labelled “UI integration fixture” and start READY. Review approval,
approve, execute, then verify. For campaigns, load the eligible audience first.
The seeder is additive: it skips existing fixtures and never clears tasks or
overwrites receipts. For a fresh run, choose a new database filename and matching
`BIZMATE_DATABASE_PATH`; no deletion/reset is required.

## Verification

```sh
npm run test:web
npm run build
uv run --project backend pytest backend/tests -q
uv run --project backend ruff check backend
uv run --project backend python backend/scripts/export_openapi.py --check
```

Focused tests cover original-language history, preference persistence, explicit
task intake, stale selections, stable message retries, exact approval inputs,
duplicate clicks, deferral/cancellation, readonly permissions, structured HTTP
errors, preserved drafts, uncertain dispatch and latest failed verification.
The packet's READY fixtures are also exercised without task creation or execution.

Observed final checks on 14 November 2026: 69 frontend tests passed; 376 backend
tests passed with one in-memory/disk-only combination skipped; TypeScript and
production build passed; Ruff and generated-contract drift checks passed. An
earlier concurrent run hit a 30-second subprocess startup timeout in the restart
test. That test passed alone in 8.10 seconds, and the subsequent full backend run
passed in 46.37 seconds without changing the timeout or test logic.

Live browser review used an isolated SQLite database: saved chat/reload; support
approval/execution; injected ticket-read failure resulting in verified=false;
successful independent recheck; and 120-recipient/24000-paise campaign approval,
execution and verification. Both fixture tasks remained VERIFYING as required by
the backend. No browser runtime errors were observed in these journeys.

Responsive browser checks passed for 18 combinations: 320/768/1440-pixel widths,
English/Hindi/Telugu and light/dark themes, with reduced motion enabled. Checks
covered horizontal overflow, composer visibility and language-picker placement.

## Remaining shared workflow dependencies

BM-07 must connect chat/intake to language detection and executable plans;
clarifications currently record events rather than resuming the graph. BM-11/12
must own settlement investigation/follow-up and verified fresh-credit closure.
BM-14 must supply guided campaign results (including delivery counts) beyond this
contract's receipt/verification shapes. BM-15 must prepare unsupported-capability
handoffs. Arbitrary `workflow_data` is intentionally not interpreted by the UI.
These are backend workflow dependencies, not hidden frontend simulations.

Devi's acceptance review is still required. This document records implemented
frontend scope, not approval of the complete MVP or BM-18's final rehearsal.
