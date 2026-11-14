# BM-02 domain and merchant-context contract

Contract version 0.4.0 defines validated entities, conversations/messages, language metadata, explicit task transitions and a trusted server-side synthetic session. Persistence, LLM planning and actual approval execution remain separate work in BM-03/BM-06/BM-07.

## Shared types

`backend/src/bizmate/domain/models.py` is authoritative. `contracts/openapi.json` and `frontend/src/api/schema.d.ts` are generated from it. Frontend aliases for Merchant, Task, TaskStatus, PlanStep, ToolExecution, Approval, Receipt, Evidence, Verification and CapabilityGap live in `frontend/src/api/types.ts`.

## Conversations and messages

- `Conversation` is a merchant-owned header with an ID, title, preferred_language and aware creation/update times.
- `Message` has its own ID, required merchant/conversation IDs, role (`user` or `assistant`), original content up to 4,000 characters, detected_language, response_language, creation time, and an optional task ID. Message role and language metadata are data and never grant identity, scopes or approval.
- `Task.conversation_id` is an optional foreign key: a conversation can have many tasks; a task can belong to at most one conversation. Null means standalone proactive/scheduled work. Repositories must resolve conversation IDs under the server's merchant context when BM-03 adds persistence.
- `ConversationThread` is a complete read snapshot, not a second source of ownership: it groups the header, messages and tasks, rejects duplicate IDs and foreign merchant/conversation records, and resolves every message task reference against its included tasks. Partial/paginated responses must not use this full-snapshot DTO without loading referenced tasks.
- The text primitive is now `domain.types.MessageText`, so `domain.models.Message` unambiguously means the entity. Existing task-intake/clarification `message` fields remain plain strings.
- Conversation, Message, MessageRole, ConversationThread, LanguageCode and LanguageContext are included as reusable OpenAPI components and generated TypeScript aliases. No conversation storage or routes are added in this domain-contract change. Current intake continues to create standalone tasks; BM-03/BM-09 will wire persisted conversations.

Fixed demo merchant resolution is unchanged: the server captures context at app creation; conversation/message IDs or roles cannot select a merchant. The existing scope and ownership boundaries still apply.

## Language and original-content contracts

- Supported codes are exactly `en` (English), `te` (Telugu) and `hi` (Hindi). Unsupported codes, regional variants and differently cased values are rejected rather than silently coerced.
- Merchant and Conversation expose `preferred_language`, defaulting to `en` for existing demo records. The fixed server demo context carries the merchant's preference into its public session contract. When BM-03 creates a conversation, it should explicitly copy the merchant preference unless a conversation-specific choice is supplied.
- LanguageContext groups `preferred_language`, `detected_language` and `response_language` for the future workflow boundary. Message exposes detected_language and response_language directly. Detection/response metadata defaults to null until known; it is not guessed from the preference or script in this domain change. Response language may differ from detected language.
- Message.content, Task.original_request, intake/clarification strings and merchant-message events retain their original code points, whitespace, tabs and line breaks. Updating language metadata never translates, trims, case-folds or normalizes the content. The frontend submits the original composer value too.
- Blank-only messages, non-string messages and original messages longer than 4,000 characters are rejected without rewriting valid input. Short titles and other display labels still use their existing trimmed text types.
- This adds metadata contracts, not automatic language detection, translation, speech or multilingual response generation. Those behaviours belong to the later orchestration/UI work.

## Validation rules

- IDs use 1-128 letters, digits, underscores or hyphens, beginning with a letter or digit. Display text is trimmed and nonempty; original message text is preserved and limited to 4,000 characters.
- Extra request fields are rejected. Callers cannot provide merchant identity, actor identity, scopes or a task status through task-intake/message/approval endpoints.
- Models are frozen snapshots. Use `with_updates(...)` for validated replacements. Collections use tuples/frozen sets. JSON still serializes these as arrays. Tool and approval payloads must contain JSON values, excluding nonfinite numbers. Repository copies detach nested dictionaries from stored state.
- Monetary values are strict integer paise. Booleans, strings and floats are rejected. Absolute amounts/costs are nonnegative; evidence, expected amount and residual support signed amounts. Values must remain within JavaScript's exact integer range, plus or minus 9,007,199,254,740,991, for the generated TypeScript number contract.
- Timestamps require a timezone. `updated_at` cannot precede creation; scheduled time cannot precede creation; a verification cannot precede its receipt.
- Approval input hashes are lowercase SHA-256 strings. Decided approvals require an actor and aware timestamp. Pending approvals cannot contain either. BM-06 must compute and bind hashes to real approved inputs at execution time.
- Plan steps and attached records carry task and merchant IDs. Task validation rejects foreign or duplicate records, missing/cyclic plan dependencies, and verification references without a matching receipt.

## Lifecycle

`domain/lifecycle.py` defines allowed edges. The generated `contracts/lifecycle.json` makes these available to the team. `transition_task` validates an edge, keeps identity unchanged, records a status event, and returns a new validated task. It rejects skipped stages, repeated states, backdated transitions and naive timestamps. Completed, escalated and failed tasks are terminal in this version; reopening needs a later explicit domain decision.

Completion requires the latest independent verification for every receipt to succeed, all plan steps done, no pending approvals, and no scheduled next run. Conflicting latest reads block completion. A verification must use a separate tool and cannot predate its receipt. These are structural minimums. BM-06/BM-11 must still verify action inputs, source authenticity and goal-specific outcomes: a support-ticket read alone must not resolve a missing settlement credit.

## Trusted merchant context

`MerchantContext` carries actor ID, merchant ID, display name, preferred language and frozen scopes. The app resolves it once from registered server-side demo configuration. HTTP headers, query parameters, request text, tool arguments and graph/model results cannot replace this context. The public Merchant model is metadata, not an execution authority.

Scopes are explicit: `tasks:read`, `tasks:write`, `tasks:approve`, `payments:read`, `customers:read`, `tickets:write`, `campaigns:write`. Missing scopes return HTTP 403. Cross-merchant tasks return 404. APIs apply ownership checks even if a repository adapter returns a foreign task. The demo context is not production authentication and still requires loopback-only local use.

## Devi's integration contract

Repository signatures now take `MerchantContext`, not caller-chosen merchant IDs:

```python
list_tasks(context) -> list[Task]
get_task(context, task_id) -> Task | None
save(context, task) -> Task
```

The memory adapter checks scopes and ownership, revalidates incoming snapshots, protects ID collisions and disallows illegal stored status changes. The future SQLite adapter must preserve these guarantees. Its transaction boundaries, durable approvals and checkpoint coordination remain BM-03.

Mock-service ports also receive the separate `MerchantContext`; methods producing task-bound evidence or receipts take a task ID as well. Implement adapters against these signatures rather than accepting an LLM-supplied merchant ID.

Tool discovery/execute also takes `MerchantContext`; handlers receive that context separately from schema-validated inputs. Top-level identity/permission parameters are rejected even if a tool schema declares them. Handlers must always use the separate context for identity, never values inside data payloads. Read scopes are enforced at execution. Writes remain blocked until BM-06 is implemented.

## Saiteja's integration contract

The session response now includes `actor_id`. Tasks include `tool_executions` and `capability_gaps`. Generated contracts add required merchant/task references on attached entities and stronger field constraints. Frontend fixtures have been updated. Regenerate types rather than copying old payload shapes. Display lifecycle state from the backend; client-side state changes do not authorize actions.

Run `npm run contracts:generate` after intentional changes and `npm run check` before review. The task stays unchecked in TASKS.md until Devi's review is accepted.
