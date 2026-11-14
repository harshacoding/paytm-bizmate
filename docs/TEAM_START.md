# Start work in parallel

The existing PRD and TASKS.md remain the build authority. This scaffold contributes the initial BM-01 setup and interfaces; it does not complete the remaining task acceptance criteria.

## Harsha

Start with `backend/src/bizmate/domain/models.py` and `contracts/openapi.json`. Agree schema changes with Devi and Saiteja, regenerate types, then implement `tools/policy.py`, registry preconditions and `agents/graph.py`. Add intent, validated plans and checkpoints. Implement `workflows/settlement.py` after the payment adapter contract is agreed.

Owned tasks: BM-02, BM-05, BM-06, BM-07, BM-08, BM-10, BM-11, BM-12.

## Devi

Start with `persistence/repository.py` and `services/ports.py`. Replace memory with SQLite and build stateful synthetic ticket, payment, customer and campaign adapters. Register them through Harsha's registry. Then implement campaign and handoff modules; Harsha owns the settlement scheduler. Own the transport routes and final integration tests.

Owned tasks: BM-03, BM-04, BM-13, BM-14, BM-15, BM-17.

## Saiteja

Start with `frontend/src/App.tsx` and `components/`. Run both services, try request intake and the error/retry UI. Replace preview components with typed workflow responses as the backend lands. Keep fixture previews clearly labelled until then. Build approval/cancel panels against Harsha's action snapshots, not frontend-only permission checks. Finish accessibility/responsive checks and demo instructions.

Owned tasks: BM-01, BM-09, BM-16, BM-18.

## First team checkpoint

1. All three run `npm run dev` and the test suite.
2. Harsha publishes agreed task, approval, receipt, verification and proof contracts.
3. Devi supplies durable task APIs and read/write mock adapter shapes.
4. Saiteja builds against those contracts and the labelled preview data.
5. Ship a settlement request through approval and separate verification before expanding to campaigns.

## Branch and review rules

- Branch from the shared scaffold: `codex/bm-06-approval-engine`, `codex/bm-03-persistence`, `codex/bm-09-task-ui`.
- Keep PRs task-sized. Include tests and any generated contract changes.
- Harsha reviews shared schema, permissions, approval, recovery and completion semantics.
- Devi reviews routine UI/service changes; Saiteja owns frontend edits unless paired explicitly.
- Devi's and Saiteja's GitHub usernames are not known. Add their real handles to CODEOWNERS when available; do not invent accounts.
- Do not add real provider credentials, live payment actions, or real marketing sends to this MVP.
