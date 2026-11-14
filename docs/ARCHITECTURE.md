# Architecture and extension points

The scaffold is one monorepo with two independently runnable applications. It provides the integration surface needed to start the 18-task backlog, not a completed MVP.

```text
React workspace -> typed API client -> FastAPI routes -> server merchant context
                                          |
                                 task repository protocol
                                          |
                                 LangGraph entry point
                                          |
                           tool registry and fail-closed policy
                                          |
                    settlement / campaign / handoff service ports
```

## Implemented now

- BM-14/15 typed campaign and handoff review APIs, revision-checked draft edits, fresh atomic audience validation, minimal support drafts, permission-gap telemetry and independent support-route verification. See [testing guide](BM14_BM15_TESTING.md).

- BM-10 deterministic source-linked settlement proof, unknown evidence handling, typed registry tool and reconciliation API.

- BM-13 deterministic consent-aware customer segmentation, typed tool registration and campaign-cost API.

- Vite/React/TypeScript workspace and FastAPI package, root commands and locked dependencies.
- Shared Pydantic models, generated OpenAPI and frontend types.
- Server-configured synthetic merchant context and merchant-scoped SQLite task adapter.
- Durable task snapshots including plans, approvals, evidence, receipts, verification, execution/error history, due times and checkpoint references.
- Dedicated merchant-scoped conversations and ordered user/assistant messages in SQLite.
- BM-07/08 structured multilingual intake, validated execution plans, SQLite LangGraph interrupts, resume, bounded safe-read recovery and uncertain-write inspection. See [implementation and testing](BM07_BM08_TESTING.md).
- Static PRD fixtures for independent frontend component work, explicitly separate from real task evidence.
- Typed registry metadata, intent/scope discovery, strict dispatch and backend preconditions; consequential execution requires exact-input approval and independent verification. See [BM-05 adapter and planner contracts](BM_05_TOOL_REGISTRY.md).
- Backend and UI tests, CI, ownership documentation and task-sized PR template.

## Deliberately unfinished

| Capability | Extension point | Owner / task |
| --- | --- | --- |
| Product tool registration and workflow integration | BM-04 adapters bind through `tools/registry.py` and the [BM-06 approval engine](BM_06_APPROVAL_ENGINE.md) | Devi BM-04 / Harsha BM-07 |
| Settlement investigation workflow | `workflows/settlement.py` | Harsha BM-11 |
| Scheduler and new-credit verification | `services/scheduler.py` | Devi BM-12 |
| Full approvals, clarification and evidence interaction | `frontend/src/components`, `App.tsx` | Saiteja BM-09/16 |

## Identity and deployment boundary

The default merchant is chosen from backend configuration, not from user text or a caller-supplied ID. Two synthetic merchants are provided for isolation tests. This is **not authentication** and must remain on a loopback interface. Add real session validation before any shared or production deployment. The Vite proxy is for local development; set a public API origin and explicit CORS allowlist when adding a deployment later.

## Persistence and completion

`SQLiteTaskRepository` implements the existing merchant-scoped `TaskRepository` protocol. A versioned SQLite schema stores each complete validated task as one JSON snapshot, with indexed merchant ownership and creation time. Each operation uses its own connection. Atomic transactions and revision checks protect concurrent updates. Both adapters accept the server-resolved `MerchantContext`, enforce scopes and ownership, and use immutable shared models with validated replacements. The memory adapter remains available for dependency injection and follows the same revision contract.

New tasks start at revision zero. `save(context, task)` returns a detached snapshot with the next revision and a refreshed `updated_at`. Callers retain that returned snapshot or reload before the next save. Saving a stale revision raises `TaskConflictError`; HTTP clients receive 409 with code `TASK_CONFLICT` and should reload before retrying their intended change. Task lists order by creation time descending, then task ID descending. Timelines preserve chronological event order with insertion order for equal timestamps. Naive timestamps are interpreted as UTC when ordering records.

Task writes persist `checkpoint_id` together with the task state. BM-07 owns the graph checkpointer, task-to-thread mapping, and coordination of checkpoint commits with task writes. BM-07 implements durable graph pause/resume, per-task process locking and replay from authoritative task phases. The task engine requires a matching receipt and successful independent verification before completing a goal. Settlement closure requires fresh matching credit evidence, and a bank change remains pending with human support.

The API supports polling through `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}` and `GET /api/v1/tasks/{task_id}/events`. Reads preserve IDs and revisions. The frontend currently refreshes manually; BM-09 can poll these same endpoints while a task view is active. Errors use `ErrorResponse` with `code`, `message` and `task_reference`, including 404 for unavailable tasks, 409 for stale writes and 422 for invalid requests.

`SQLiteConversationRepository` owns the `conversations` and `messages` tables in the same configured database. Conversation creation, listing, retrieval, language updates and message history use the server-selected merchant. A composite foreign key also enforces message ownership within SQLite. User and assistant messages commit together, with a per-conversation sequence that keeps concurrent turns ordered. Conversations list by creation time ascending and conversation ID as a stable tie breaker. An optional `client_message_id` reuses the saved response on retry and returns HTTP 409 if reused with different user content or explicit language metadata.

Original user and assistant text, UTC timestamps and language tags persist with each message. Conversation preference defaults to `en`, and incoming messages inherit it when their language is omitted. Messages persist separate `detected_language` and `response_language` fields from the shared BM-02 contract. BM-07 supplies actual detected language and localized response language. A legacy `language` hint remains available for older clients. Preference changes apply to subsequent messages and preserve existing history. Startup adds language columns to existing chat tables, marking historical message language as `und`. Task schema version 2 adds an optional indexed `conversation_id`, with migration from version 1.

Conversation requests accept user content. The backend supplies the assistant role and localized intake response. Business tasks keep their own IDs, status, due times and checkpoint references. Task creation validates optional conversation association against merchant ownership. That association is informational, with no cascading foreign key into task storage. Conversation IDs are excluded from task/checkpoint identity. Reopening or removing a conversation therefore preserves persisted task state and its original association. Business execution starts through the task API, while the conversation-message API retains its lightweight intake contract. Durable LangGraph checkpoints are stored separately from chat history.

## Reading references

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Vite guide](https://vite.dev/guide/)
