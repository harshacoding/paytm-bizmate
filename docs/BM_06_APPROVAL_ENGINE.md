# BM-06 approval and verification engine

This branch builds on BM-05. It implements action approval, durable execution claims, receipts and separate verification reads using the existing task repository. No new dependencies or database migrations are needed. Production authentication and product mock adapters are outside this change.

## Integration

The app owns a `ToolRegistry` at `app.state.tools` and registers BM-04 synthetic adapters at startup. Tests or bootstrap code can supply a registry with `create_app(tools=registry)`; startup preserves that injected registry. `ApprovalEngine(repository, registry)` is also callable directly from BM-07.

The ticket adapter accepts `task_id` and `summary`. The campaign adapter accepts `task_id`, the exact `message`, `recipient_ids` and `cost_paise`; approval covers these values instead of an opaque draft hash. Both accept execution keys only from the engine. The engine rejects an input task ID that differs from the approved task. Campaign consent is rechecked by the provider at dispatch. Status/delivery adapters read stored mock actions and return scoped verification results.

Register a side-effect adapter with an input `Model`, output `ActionResult`, write scopes, relevant intents, approval requirement, `key_required` idempotency and its separate verification read. Its synchronous handler accepts `(context, inputs, *, idempotency_key)` and returns `ActionResult(external_reference=...)`. The engine supplies the key; model arguments cannot authorize a write. An adapter must forward this key to its stateful mock service and never derive authority from message content.

Register the verification read first. It takes a `reference` string and returns `VerificationResult(merchant_id, task_id, external_reference, verified, evidence_reference)` by querying stored external state. The engine checks those identifiers against its saved receipt. A write response cannot supply the verification result. Both adapters must scope every query to the supplied merchant context. Use backend predicates for resource ownership, evidence availability and consent revalidation.

BM-07 must create a task with a supported intent and bring it to READY or RUNNING before requesting approval. New chat requests still use the scaffold graph; this change does not implement workflow planning or UI approval controls.

## HTTP contract

All routes below use `/api/v1/tasks/{task_id}` as their prefix. Task ownership is checked using the server-resolved session. Approval decisions and execution require `tasks:approve`; every state-changing operation also requires task read/write scopes. Action and verification permissions are checked again before executing.

| Method and suffix | Body | Response |
| --- | --- | --- |
| POST `/approvals` | `{"action":"create_support_ticket","inputs":{...}}` | 201 `Approval`, including exact snapshot and hash |
| POST `/approvals/{approval_id}` | `{"decision":"approve","input_hash":"..."}` or `cancel` | 200 decided `Approval` |
| POST `/approvals/{approval_id}/execute` | `{"inputs":{...}}` | 200 saved `Receipt` |
| POST `/receipts/{receipt_id}/verify` | No body | 200 saved `Verification` |

Task detail and event endpoints expose pending approvals, decisions, receipts, verification results and the next action. Failures use the existing error envelope: 403 for permissions, 404 for unavailable scoped records/tools, 409 for conflicting state or failed preconditions, and 422 for invalid action inputs. Unknown approval IDs now return 404 instead of the old placeholder 501.

## Approval and execution rules

- Snapshots contain validated/defaulted JSON inputs and preserve original message text. SHA-256 binds the canonical inputs, action, task and merchant. A different body or hash cannot reuse approval.
- Only one approval can be pending at a time. Approving stores actor and decision time and moves the task to READY. The executing session must retain the required scopes and match the approving actor.
- Cancellation before execution moves the task back to PLANNING. Cancelled approval cannot be revived; changed inputs require a new approval. Repeating the same decision is harmless. Claimed/executed actions cannot be cancelled retroactively.
- Repository saves preserve approval snapshots and append-only execution, receipt and verification records. Existing rows are preserved; stale revisions fail before any write adapter is called.
- A deterministic key derived from merchant, task and approval IDs is saved as an uncertain execution claim before dispatch. Optimistic concurrency allows one caller to claim an action. Successful dispatch adds a receipt and a success record and moves the task to VERIFYING.
- Replaying the same approved action returns its stored receipt without invoking the adapter. Replaying a claim with no receipt returns a conflict. A timeout, invalid response or process interruption might follow an external write, so the engine never automatically dispatches that claim again.
- Verification invokes the registered separate read. Missing state, mismatched identifiers, read errors and malformed results cannot verify the action. A failed verification is recorded, keeps the task unresolved and can be checked again without resending the action.
- A receipt alone cannot complete a task. The latest verification must succeed for every receipt, and no uncertain execution may remain unresolved. Even successful action verification leaves the task in VERIFYING: BM-07/BM-11 must separately decide whether the actual task goal is met. Ticket creation does not prove a settlement credit arrived.

## Recovery boundary

If the process dies after claiming but before writing, the claim also remains unresolved. If task revision changes after a successful external write, saving the receipt can conflict; the prior claim still prevents another dispatch. Inspect external state and reconcile the saved claim before proceeding. BM-08 supplies that recovery workflow; there is no automatic claim reset or unsafe retry endpoint here.

The in-memory repository supports isolated tests only. Restart protection uses the normal SQLite repository. Resetting or replacing a database loses its deduplication history and is not a safe recovery action.

## Checks

`backend/tests/test_approvals.py` uses a separate SQLite ticket mock to prove that verification reads stored state. Tests cover exact snapshots, changed/cancelled/missing approvals, scopes, actors, merchant isolation, consent-style predicates, decision replay, concurrent claims, external timeouts, malformed responses, restart persistence, conflicting receipt saves, independent verification failure and the HTTP contract. The existing registry and persistence suites remain part of `npm run check`.
