# Paytm BizMate

**Your AI teammate for business.** Monorepo for the Paytm hackathon MVP: settlement investigation, customer win-back, and honest support handoff.

## Connected merchant workspace

The default screen at <http://127.0.0.1:5173> uses the local API for merchant context, durable conversations, messages, tasks, exact-input approvals, execution receipts and independent verification. Start both apps using the quick-start commands below.

Chat and business tasks are separate in the supplied API contract. Send saves a conversation turn; **Start a task from this question** creates a tracked task. New intake now runs the BM-07/BM-08 orchestrator and pauses for clarification or exact approval. Approved work continues through the task-resume endpoint, with backend-owned execution, bounded recovery and independent verification. Under **Your tasks**, reopen work, inspect its next action and timeline, add clarification, or review a backend-prepared approval. Approve, execute and verify are distinct steps. A verified support ticket does not prove a missing bank credit has arrived.

English, Hindi and Telugu selection persists as a conversation fallback preference. The UI preserves saved messages and uses the server-returned response language; the backend resolves English/Hindi/Telugu from each incoming message, using the selected preference when detection is uncertain. Light/dark themes, the compact composer, upward language picker, adjustable history panel and numeric unread badges remain available.

**Speak** streams microphone audio through FastAPI to ElevenLabs Scribe v3 Live. Copy backend/.env.example to backend/.env and set BIZMATE_ELEVENLABS_API_KEY locally. The key stays on the server. Done lets the merchant review/edit; Send submits the draft. A missing key or microphone failure preserves the draft. Live provider accuracy requires testing with a configured key.

The original timed walkthrough is available under **Sample walkthrough**, or at <http://127.0.0.1:5173/?demo=1>. It remains a browser-only simulation of the five merchant journeys, sales reports and bank support. Its simulated outcomes are not backend receipts or financial evidence.

See the [BM-09/BM-16 integration and review guide](docs/BM09_BM16_UI_INTEGRATION.md) for the API boundary, exact approval semantics, isolated READY fixtures and verification evidence.

## Quick start

Install Node.js 22.14+ (22.x or 24.x), Python 3.11-3.13, and [uv](https://docs.astral.sh/uv/getting-started/installation/). From the repository root:

```sh
npm ci
uv sync --project backend --locked --extra dev
npm run dev
```

- Workspace: <http://127.0.0.1:5173>
- API documentation: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>

On Windows PowerShell, use `npm.cmd` if execution policy blocks `npm.ps1`; changing policy is unnecessary. Stop servers with Ctrl+C. To run separately, use `npm run dev:api` and `npm run dev:web` in separate terminals.

The offline planner and synthetic workflows require no model key. Voice dictation requires the optional backend speech key. Optional settings: copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`. Keep secrets on the backend; frontend `VITE_` configuration is public. Both development servers bind to loopback. Synthetic merchant selection is a local development convenience, not authentication.

## Implemented capabilities

- Connected React/TypeScript chat with server conversation history, multilingual task details, exact approval/cancel/defer controls, timelines, evidence, receipts and verification timestamps. An explicitly separate sample walkthrough remains available.
- FastAPI task create/list/detail/events/messages, synthetic session and health endpoints, plus durable LangGraph execution and a task resume endpoint.
- Merchant-scoped SQLite task storage, typed domain/service interfaces, fail-closed action boundaries, generated OpenAPI/frontend types, tests, CI, and ownership docs.
- Typed tool registry with intent/scope discovery, strict input/output validation and executable preconditions. BM-04 adapters are registered and connected through validated backend plan templates. See [BM-05 integration contract](docs/BM_05_TOOL_REGISTRY.md).

The [BM-06 approval engine](docs/BM_06_APPROVAL_ENGINE.md) provides exact-input approve/cancel APIs, durable execution claims, replay protection, receipts and independent verification. BM-04 synthetic adapters are connected; writes require approval through the engine. Workflow planning is connected. The connected UI supports exact approval and explicit continuation through orchestration. Unknown approvals return HTTP 404.

**BM-07/08 implemented:** structured intent extraction, multilingual clarification and summaries, validated workflow steps, durable checkpoints, approval/input pause and resume, bounded reads, source fallback and uncertain-write inspection. See [BM-07/BM-08 implementation and testing](docs/BM07_BM08_TESTING.md) for commands, model configuration and remaining integration. Default intent extraction uses an offline demo parser, with optional OpenAI structured extraction. Scheduling and fresh-credit closure remain separate workflow tasks. Static previews remain separate from task evidence.

Task records and their timelines survive backend restart/reload in `backend/.data/bizmate.sqlite3`. Set `BIZMATE_DATABASE_PATH` to select another file. Relative paths resolve from `backend/`. Startup creates the database and seeds the example task once, preserving subsequent edits. Local database files stay outside Git.

BM-14 adds editable campaign review, fresh eligibility/consent checks and independently verified delivery. BM-15 adds minimal approved human-support handoffs with verified routing and honest pending status. See [BM-14/BM-15 API flow and test commands](docs/BM14_BM15_TESTING.md). BM-09 UI changes are separate.

BM-17 adds a repeatable backend policy evaluation with local JSON/JUnit evidence and CI console results. Run `npm run evaluate:policy`. See [BM-17 coverage, observed results and pending acceptance](docs/BM17_EVALUATION.md).

## Conversation API

Source-linked settlement reconciliation is available through `POST /api/v1/settlements/reconcile`. See [BM-10 testing](docs/BM10_TESTING.md) for expected proof amounts and commands.

Synthetic service APIs, fixture commands and the demo clock are documented in [BM-04 testing](docs/BM04_TESTING.md).

Customer segmentation and campaign cost are available through `POST /api/v1/campaigns/segment`. See [BM-13 testing](docs/BM13_TESTING.md) for expected results and commands.

Conversations and user/assistant message history persist in the same database. Open <http://127.0.0.1:8000/docs> and expand **conversations** to test the routes. The server resolves merchant ownership for every operation.

| Method | Route                                 | Result                                                    |
| ------ | ------------------------------------- | --------------------------------------------------------- |
| POST   | `/api/v1/conversations`               | Create a conversation with a title and preferred language |
| GET    | `/api/v1/conversations`               | List this merchant's conversations, oldest first          |
| GET    | `/api/v1/conversations/{id}`          | Retrieve conversation details                             |
| PATCH  | `/api/v1/conversations/{id}`          | Update this conversation's preferred language             |
| GET    | `/api/v1/conversations/{id}/messages` | Retrieve ordered user and assistant history               |
| POST   | `/api/v1/conversations/{id}/messages` | Save user content and the backend assistant reply         |

Run these commands from the repository root after starting the API.

```sh
curl -sS -X POST http://127.0.0.1:8000/api/v1/conversations \
  -H 'Content-Type: application/json' \
  -d '{"title":"Settlement questions","preferred_language":"te"}'
```

Copy the returned `conversation_id` into the following commands.

```sh
conversation_id=PASTE_CONVERSATION_ID
curl -sS -X POST "http://127.0.0.1:8000/api/v1/conversations/$conversation_id/messages" \
  -H 'Content-Type: application/json' \
  -d '{"content":"నా సెటిల్మెంట్ ఎందుకు తక్కువగా వచ్చింది?","language":"te","client_message_id":"test-turn-1"}'
curl -sS "http://127.0.0.1:8000/api/v1/conversations/$conversation_id/messages"
curl -sS -X PATCH "http://127.0.0.1:8000/api/v1/conversations/$conversation_id" \
  -H 'Content-Type: application/json' -d '{"preferred_language":"hi"}'
curl -sS -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"Investigate my settlement\",\"conversation_id\":\"$conversation_id\"}"
curl -sS "http://127.0.0.1:8000/api/v1/tasks?conversation_id=$conversation_id"
```

Repeating a request with the same `client_message_id` and content returns the stored turn. Restart the API and retrieve history again to verify persistence. Original user/assistant text, timestamps and message languages remain available. Preferred language defaults to `en`; a user message inherits it when `language` is omitted. Messages also expose the shared `detected_language` and `response_language` fields. BM-07 detects the actual input language and generates an English, Telugu or Hindi reply, using preference when detection is uncertain. The legacy `language` field retains declared hints for compatibility. Language metadata and preferences persist alongside multilingual generation. Existing message records gain `und` for unknown historical language during migration.

Task creation accepts an optional `conversation_id` belonging to the current merchant. Tasks created before this addition keep a null association. Task state, due times and checkpoint references have their own lifecycle. Task execution and checkpoint recovery persist independently of the conversation lifetime. Harsha reviews BM-03 acceptance.

```sh
uv run --project backend pytest backend/tests/test_chat_persistence.py -q
sqlite3 backend/.data/bizmate.sqlite3 '.schema conversations'
sqlite3 backend/.data/bizmate.sqlite3 '.schema messages'
sqlite3 -header -column backend/.data/bizmate.sqlite3 \
  'SELECT merchant_id, conversation_id, sequence, role, language, created_at, content FROM messages ORDER BY conversation_id, sequence;'
sqlite3 -header -column backend/.data/bizmate.sqlite3 \
  'SELECT conversation_id, merchant_id, preferred_language FROM conversations ORDER BY created_at;'
sqlite3 -header -column backend/.data/bizmate.sqlite3 \
  'SELECT task_id, merchant_id, conversation_id, revision FROM tasks;'
```

## Structure and ownership

```text
frontend/src/                 Saiteja
  api/                       Typed client and generated API schema
  components/                Timeline and preview cards
  test/                      UI tests and contract-shaped fixtures
backend/src/bizmate/
  domain/                    Harsha: shared contracts and errors
  agents/                    Harsha: LangGraph entry point
  tools/                     Harsha: registry and approval policy
  workflows/                 Settlement (Harsha), campaign/handoff (Devi)
  persistence/               Devi: repository interface and SQLite adapter
  services/                  Devi: mock ports, fixtures, scheduler
  api/                       Devi: scoped HTTP transport
backend/tests/               API and fail-closed policy checks
backend/scripts/             OpenAPI export
contracts/                   Shared OpenAPI schema
.github/                     CI, ownership and PR template
docs/                        Architecture, onboarding and smoke check
```

| Developer | Start here                                                         | Tasks                         |
| --------- | ------------------------------------------------------------------ | ----------------------------- |
| Harsha    | Domain contracts, registry/policy, agent graph, settlement         | BM-02, 05, 06, 07, 08, 10, 11 |
| Devi      | Repository, service ports/mocks, APIs, scheduler, campaign/handoff | BM-03, 04, 12, 13, 14, 15, 17 |
| Saiteja   | App, components, client, UI tests and demo docs                    | BM-01, 09, 16, 18             |

Read [Team start](docs/TEAM_START.md) before editing shared contracts. UI work can use fixtures while services are implemented. The scaffold supplies initial setup; task ownership and review requirements remain unchanged.

## Checks and contracts

```sh
npm run check
npm run contracts:generate
```

`check` runs backend lint, API/policy tests, UI tests, TypeScript, the frontend production build and OpenAPI drift validation. CI also regenerates frontend types and rejects drift. Commit generated `contracts/openapi.json` and `frontend/src/api/schema.d.ts` with schema changes. Do not edit generated files by hand.

Individual commands: `npm run test:api`, `npm run test:web`, `npm run typecheck`, `npm run lint:api`, `npm run build`, `npm run contracts:check`. Format with `npm run format` and `npm run format:api`.

Use `npm install --workspace frontend ...` and `uv add --project backend ...` for intentional dependency changes. Commit `package-lock.json` and `backend/uv.lock`; they pin the dependency graph. `npm run build` writes `frontend/dist`. Deployment requires a separately configured API and proper session security; deployment is outside this scaffold.

## Product and planning

- [Complete PRD](Paytm_BizMate_Complete_PRD.docx)
- [18 implementation tasks](TASKS.md)
- [Team ownership and handoffs](TEAM_PLAN.md)
- [Architecture and unfinished extension points](docs/ARCHITECTURE.md)
- [Developer smoke check](docs/DEMO.md)

First full product milestone: the Rs 166.80 settlement investigation through approved support ticket, restart-safe follow-up, and verified fresh credit. All MVP records and external actions remain synthetic or simulated.
