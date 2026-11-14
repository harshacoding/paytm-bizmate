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

**Pending implementation:** LLM intent, workflow execution, durable graph checkpoints, approval execution, tickets, scheduling, reconciliation, segmentation, campaign sends and delivery verification. Requests remain awaiting implementation. Approval decisions return HTTP 501; the send button is disabled. Static previews are separate from task evidence.

Task records and their timelines survive backend restart/reload in `backend/.data/bizmate.sqlite3`. Set `BIZMATE_DATABASE_PATH` to select another file. Relative paths resolve from `backend/`. Startup creates the database and seeds the example task once, preserving subsequent edits. Local database files stay outside Git.

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
