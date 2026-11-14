# Paytm BizMate

**Your AI teammate for business.** Monorepo for the Paytm hackathon MVP: settlement investigation, customer win-back, and honest support handoff.

## Connected merchant workspace

The default screen at <http://127.0.0.1:5173> uses the local API for merchant context, durable conversations, messages, tasks, exact-input approvals, execution receipts and independent verification. Start both apps using the quick-start commands below.

Chat and business tasks are separate in the supplied API contract. Send saves a conversation turn; **Start a task from this question** creates a tracked task. New intake currently waits for BM-07. Under **Your tasks**, reopen work, inspect its next action and timeline, add clarification, or review a backend-prepared approval. Approve, execute and verify are distinct steps. A verified support ticket does not prove a missing bank credit has arrived.

English, Hindi and Telugu selection persists as a conversation fallback preference. The UI preserves saved messages and uses the server-returned response language; the current backend scaffold replies in English until BM-07 implements generation. Light/dark themes, the compact composer, upward language picker, adjustable history panel and numeric unread badges remain available.

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

Typed chat and synthetic API actions require no model key. Voice dictation requires the optional backend speech key. Optional settings: copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env`. Keep secrets on the backend; frontend `VITE_` configuration is public. Both development servers bind to loopback. Synthetic merchant selection is a local development convenience, not authentication.

## Implemented capabilities and workflow boundaries

- React/TypeScript connected chat and task workspace, plus a separate sample walkthrough.
- Merchant-scoped SQLite conversation/task persistence, scoped APIs, generated types and structured errors.
- Exact-input approvals, simulated execution, independent verification, source-linked settlement proof and server segmentation/costs.
- Task timelines, clarification, pending/failed/escalated states, receipts, verification timestamps, evidence and handoff panels.

**Shared workflow dependencies:** BM-07 language detection/planning/resumption, BM-08 recovery orchestration, BM-11/12 guided settlement follow-up/closure, BM-14 guided campaign outcomes and BM-15 automated handoff preparation. The current chat graph records messages and returns scaffold guidance; it does not manufacture READY plans. Tasks and conversations survive restart. Static previews remain separate from task evidence.

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
  persistence/               Devi: repository interface and SQLite adapters
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
