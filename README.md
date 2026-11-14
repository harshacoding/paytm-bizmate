# Paytm BizMate

**Your AI teammate for business.** Monorepo for the Paytm hackathon MVP: settlement investigation, customer win-back, and honest support handoff.

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

No API key is required. Optional settings: copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`. Keep secrets on the backend; frontend `VITE_` configuration is public. Both development servers bind to loopback. Synthetic merchant selection is a local development convenience, not authentication.

## Scaffold capabilities

- React/TypeScript workspace with task navigation, request intake, timeline, loading/error/retry states, and labelled settlement/campaign component previews.
- FastAPI task create/list/detail/events/messages, synthetic session and health endpoints, plus a minimal LangGraph entry point.
- Merchant-scoped SQLite task storage, typed domain/service interfaces, fail-closed action boundaries, generated OpenAPI/frontend types, tests, CI, and ownership docs.
- Typed tool registry with intent/scope discovery, strict input/output validation and executable preconditions. BM-04 adapters are registered; planner integration remains pending. See [BM-05 integration contract](docs/BM_05_TOOL_REGISTRY.md).

**Pending implementation:** LLM intent, workflow execution, durable graph checkpoints, approval execution, tickets, scheduling, reconciliation, segmentation, campaign sends and delivery verification. Requests remain awaiting implementation. Approval decisions return HTTP 501; the send button is disabled. Static previews are separate from task evidence.

Task records and their timelines survive backend restart/reload in `backend/.data/bizmate.sqlite3`. Set `BIZMATE_DATABASE_PATH` to select another file. Relative paths resolve from `backend/`. Startup creates the database and seeds the example task once, preserving subsequent edits. Local database files stay outside Git.

## Conversation API

Synthetic service APIs, fixture commands and the demo clock are documented in [BM-04 testing](docs/BM04_TESTING.md).

Conversations and user/assistant message history persist in the same database. Open <http://127.0.0.1:8000/docs> and expand **conversations** to test the routes. The server resolves merchant ownership for every operation.

| Method | Route | Result |
| --- | --- | --- |
| POST | `/api/v1/conversations` | Create a conversation with a title and preferred language |
| GET | `/api/v1/conversations` | List this merchant's conversations, oldest first |
| GET | `/api/v1/conversations/{id}` | Retrieve conversation details |
| PATCH | `/api/v1/conversations/{id}` | Update this conversation's preferred language |
| GET | `/api/v1/conversations/{id}/messages` | Retrieve ordered user and assistant history |
| POST | `/api/v1/conversations/{id}/messages` | Save user content and the backend assistant reply |

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

Repeating a request with the same `client_message_id` and content returns the stored turn. Restart the API and retrieve history again to verify persistence. Original user/assistant text, timestamps and message languages remain available. Preferred language defaults to `en`; a user message inherits it when `language` is omitted. Messages also expose the shared `detected_language` and `response_language` fields. Detection stays null until supplied by BM-07. The current scaffold assistant responds in English and records response language `en`. The legacy `language` field retains declared hints for compatibility. Language metadata and preference storage work independently of BM-07 multilingual generation. Existing message records gain `und` for unknown historical language during migration.

Task creation accepts an optional `conversation_id` belonging to the current merchant. Tasks created before this addition keep a null association. Task state, due times and checkpoint references have their own lifecycle. Test history persistence locally with the existing scaffold; full graph execution recovery depends on Harsha's BM-07 checkpointer integration. Harsha reviews BM-03 acceptance.

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

| Developer | Start here | Tasks |
| --- | --- | --- |
| Harsha | Domain contracts, registry/policy, agent graph, settlement | BM-02, 05, 06, 07, 08, 10, 11 |
| Devi | Repository, service ports/mocks, APIs, scheduler, campaign/handoff | BM-03, 04, 12, 13, 14, 15, 17 |
| Saiteja | App, components, client, UI tests and demo docs | BM-01, 09, 16, 18 |

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
