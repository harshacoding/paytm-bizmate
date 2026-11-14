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

- Vite/React/TypeScript workspace and FastAPI package, root commands and locked dependencies.
- Shared Pydantic models, generated OpenAPI and frontend types.
- Server-configured synthetic merchant context and merchant-scoped memory task adapter.
- Request intake through a minimal LangGraph node; saved request history and task timeline.
- Static PRD fixtures for independent frontend component work, explicitly separate from real task evidence.
- Policy/registry boundaries that reject consequential execution while it is unfinished.
- Backend and UI tests, CI, ownership documentation and task-sized PR template.

## Deliberately unfinished

| Capability | Extension point | Owner / task |
| --- | --- | --- |
| Durable tasks and events | `persistence/repository.py`: implement SQLite behind `TaskRepository` | Devi BM-03 |
| Stateful mock integrations and fixtures | `services/ports.py`, `services/demo.py` | Devi BM-04 |
| Full tool metadata and approved execution | `tools/registry.py`, `tools/policy.py` | Harsha BM-05/06 |
| LLM intent, plans, checkpoint/resume and recovery | `agents/graph.py` | Harsha BM-07/08 |
| Deterministic reconciliation and settlement workflow | `workflows/settlement.py` | Harsha BM-10/11 |
| Scheduler and new-credit verification | `services/scheduler.py` | Devi BM-12 |
| Segmentation and approved campaign simulation | `workflows/campaign.py` | Devi BM-13/14 |
| Confirmed human handoff | `workflows/handoff.py` | Devi BM-15 |
| Full approvals, clarification and evidence interaction | `frontend/src/components`, `App.tsx` | Saiteja BM-09/16 |

## Identity and deployment boundary

The default merchant is chosen from backend configuration, not from user text or a caller-supplied ID. Two synthetic merchants are provided for isolation tests. This is **not authentication** and must remain on a loopback interface. Add real session validation before any shared or production deployment. The Vite proxy is for local development; set a public API origin and explicit CORS allowlist when adding a deployment later.

## Persistence and completion

The memory adapter resets on backend restart or reload. No durable recovery is claimed. Devi should implement durable repositories and agree checkpoint boundaries with Harsha. The eventual task engine must require matching receipt plus independent verification before completing a goal. Ticket existence is not settlement resolution; bank change must remain pending with human support. Static preview records are never completion evidence.

## Reading references

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Vite guide](https://vite.dev/guide/)
