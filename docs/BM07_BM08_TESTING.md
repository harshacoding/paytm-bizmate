# BM-07 and BM-08 implementation and testing

Both tasks are implemented on `codex/bm-07-08-orchestration-recovery`, based on main `8cbe069`.

## Start and test

From the repository root, with the existing Node and uv setup:

```sh
npm run dev
```

Swagger: http://127.0.0.1:8000/docs

In a second terminal:

```sh
# Prepare source evidence and pause for approval
python3 backend/scripts/smoke_orchestration.py

# Approve a new synthetic ticket and verify it independently
python3 backend/scripts/smoke_orchestration.py --approve

# Exhaust the report's three read attempts, recover from separate sources,
# then inspect a ticket recorded just before a provider timeout
python3 backend/scripts/smoke_orchestration.py --approve --report-timeouts 3 --write-timeout

# Approved campaign with a committed-write timeout and independent delivery verification
python3 backend/scripts/smoke_orchestration.py --workflow campaign --approve --write-timeout

# Full checks, including process-restart recovery regressions
npm run check
# Only BM-07/BM-08 regressions
uv run --project backend pytest backend/tests/test_orchestration_recovery.py -q
```

The smoke script prints the task ID, status, checkpoint ID, receipts, verification records and event URL. Its approval flag approves the exact snapshot returned by the server for this new synthetic task. Failure controls require `BIZMATE_DEMO_CONTROLS_ENABLED=true`.

Expected settlement output is ₹18,566.80 expected, ₹18,400.00 credited and ₹166.80 unexplained. Before approval, there is no write receipt. After approval and resume, one support-ticket receipt and one independent ticket-status verification are attached. The task stays `WAITING_EXTERNAL`. A support ticket does not resolve a missing settlement credit.

The campaign example produces 120 eligible consenting customers, ₹240 cost, 118 delivered and 2 failed. Completion confirms the delivery attempt and counts. It does not claim that every message delivered or that sales increased.

## API flow

1. `POST /api/v1/tasks` with `{"message":"Why is my settlement short?"}`. An owned `conversation_id` is optional.
2. Inspect `workflow_data.settlement_proof`, `evidence`, `plan`, `next_action` and `approvals`. The task pauses at `AWAITING_APPROVAL` with an actual durable checkpoint.
3. `POST /api/v1/tasks/{task_id}/approvals/{approval_id}` with `{"decision":"approve","input_hash":"COPY_EXACT_RETURNED_HASH"}`. Cancellation uses `"cancel"`.
4. `POST /api/v1/tasks/{task_id}/resume` with no request body. The engine reloads the server-side approval, executes its immutable snapshot, then independently reads its provider reference.
5. Read `GET /api/v1/tasks/{task_id}` or `/events`. Stop and restart the API using the same database, then resume the same task. Completed writes retain the same receipt and provider action.

Ambiguous requests pause at `AWAITING_INPUT`. Clarify with `POST /api/v1/tasks/{task_id}/messages` and `{"message":"your clarification"}`. An offer without exact merchant text asks for `message="your offer"`. A message saying “approve” does not make an approval decision. Messages can change the response language without changing approved inputs.

`POST /api/v1/conversations/{conversation_id}/messages` now prepares supported workflows automatically and persists their `task_id` on both messages. General questions return a direct reply without creating a task. A clarification continues the single waiting task in that conversation. Stable client message IDs, scoped workflow IDs and per-conversation locks recover retries without duplicate preparation or writes, including a crash before the chat pair is committed. Explicit approval/execute controls remain required; text such as “approve it” grants no authority. The standalone task API remains available.

## Natural-language modes and language context

Default `BIZMATE_PLANNER_MODE=demo` uses a deterministic offline parser. It supports the documented English, Telugu, Hindi and mixed-script examples. It deliberately asks for clarification on unrecognized phrasing. It is not a live LLM.

Examples:

- `Why is my settlement short?`
- `నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది?`
- `मेरा सेटलमेंट कम क्यों आया है?`
- `నా సెటిల్‌మెంట్ ఎందుకు తక్కువగా ఉంది please`
- `Send inactive customers message="Come back for 10% off"`
- `Change my registered bank account`

Each incoming message chooses the response language from the dominant detected language. Ties or text without detectable words use the selected conversation language for intake, or the prior response language on task resume. Original requests and clarification events remain verbatim. Structured goals, input language, response language, read budgets, evidence, approval summaries and workflow phase persist in the task snapshot. Clarifications, approval summaries, progress, errors and final summaries have English/Telugu/Hindi templates. Tool inputs, scopes, recipients, costs and reconciliation arithmetic are server-owned and independent of presentation language.

To use Sarvam structured extraction, configure these server-only settings in `backend/.env` and restart:

```dotenv
BIZMATE_PLANNER_MODE=sarvam
BIZMATE_PLANNER_MODEL=sarvam-105b
BIZMATE_SARVAM_API_KEY=your-sarvam-subscription-key
```

The adapter uses the subscription-key header and strict JSON Schema described in [Sarvam's API reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1). Reasoning is disabled using JSON `null` (not the rejected string `"none"`) and output is capped at 4096 tokens. Responses are revalidated, and truncated completions cannot become a plan. Provider-specific credentials never cross endpoints. Keep keys only in the ignored backend `.env`; never commit a real key. Use a new task to test a model change because saved tasks reuse their extraction/checkpoints.

OpenAI remains an alternative configuration:

```dotenv
BIZMATE_PLANNER_MODE=openai
BIZMATE_PLANNER_MODEL=gpt-4o-mini
BIZMATE_OPENAI_API_KEY=your-server-api-key
```

The model receives user text as untrusted content, with a strict goal-extraction schema. It cannot return executable tools, merchant identity, permissions, money calculations or approval decisions. The server revalidates the output and copies an offer only if it appears in merchant input. Invalid output, refusal, missing credentials or provider errors pause for clarification with a saved public error event. The provider call has a 15-second timeout. Model integration is covered with mocked HTTP responses, including Sarvam header/endpoint/schema checks, provider errors and an approval-gated agent integration test. Live Sarvam execution needs a locally supplied key; mock tests do not validate account/model access.

## Checkpoints and recovery

`agents/orchestrator.py` owns one LangGraph with dispatch and interrupt nodes. The registry validates backend-owned plan templates. The BM-06 approval engine owns all consequential writes. The graph only stores task identity and routing state, and always reloads trusted merchant context, current task phase and immutable approvals from the repository.

The configured task database remains `backend/.data/bizmate.sqlite3` by default. LangGraph saves its checkpoints to the sibling `bizmate-checkpoints.sqlite3`. Checkpoint threads are derived from merchant ID and task ID. Per-task process locks serialize graph calls, and task revision checks reject conflicting snapshots. Database files and lock files stay outside Git. Keep both SQLite files when retaining a demo environment.

Task phases and execution claims are saved before dispatch. Interrupts persist the checkpoint before the HTTP response returns, and `Task.checkpoint_id` references that checkpoint. Task records and graph checkpoints use separate commits. Recovery consults the authoritative task and provider records when a process exits between those commits. This includes crashes after a write or after verification but before the final status update.

Safe read/preparation tools have a persisted maximum of three attempts per exact tool/input pair. Each attempt is claimed before the call. Only transient timeouts and connection errors retry. Validation, scope and conflicting-evidence failures escalate. Successful read results are saved and reused on replay. Report exhaustion selects a recorded fallback through separate transaction, deduction and credit tools, preserving source references and exact integer-paise arithmetic. Missing or conflicting components retain unknown amounts and cannot produce an approved shortfall action or false completion.

An uncertain write is never automatically resent. Recovery reads the provider's action by server idempotency key, checks merchant, task, action, full approved inputs and both provider/approval hashes, then attaches its recovered receipt. A separate verification read is still required. Missing or inconsistent provider evidence escalates with the unresolved execution intact. Error events, failed executions, read-attempt counts, fallback selection and recovered-write events remain visible in persisted history.

Regression tests cover separate OS processes exiting immediately after both provider write types commit, as well as clarification/approval restart, ownership, malicious extraction, exact proof amounts, language switching, cancellation, bounded fallback and verification, missing/conflicting evidence, task locks and conversation-independent checkpoints.

## Remaining integration

The shared BM-07/08 engine is usable through the APIs now. The current UI starts tasks and displays their timelines. Rich clarification/approval controls and proof cards remain frontend work. Automatic due-task scheduling and fresh-credit closure remain BM-12. BM-14/15 now extend campaign review and human handoff through the [dedicated backend workflows](BM14_BM15_TESTING.md). Broader BM-11 integration and reviewer sign-off remain separate backlog items.
