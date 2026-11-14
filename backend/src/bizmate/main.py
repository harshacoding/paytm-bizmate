from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bizmate.agents.graph import build_graph
from bizmate.api.routes import router
from bizmate.config import Settings
from bizmate.domain.errors import FeaturePending
from bizmate.domain.models import ErrorResponse, Task, TaskEvent
from bizmate.persistence.repository import MemoryTaskRepository, TaskRepository
from bizmate.services.demo import MERCHANTS


def create_app(settings: Settings | None = None, repo: TaskRepository | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.demo_merchant_id not in MERCHANTS:
        raise ValueError("Unknown synthetic merchant; choose merchant_demo or merchant_other")
    app = FastAPI(
        title="Paytm BizMate API",
        version="0.1.0",
        description="Local scaffold. Memory storage, synthetic fixtures, no live actions or LLM.",
    )
    app.state.settings = settings
    app.state.tasks = repo if repo is not None else MemoryTaskRepository()
    app.state.graph = build_graph()
    if repo is None:
        app.state.tasks.save(
            Task(
                task_id="demo-settlement",
                merchant_id="merchant_demo",
                goal="Investigate a short settlement",
                original_request="Why is my settlement short?",
                next_action="Submit a request to try task intake. Execution is pending BM-07.",
                events=[
                    TaskEvent(
                        kind="demo_seed", message="Synthetic example; no investigation has run."
                    )
                ],
            )
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(FeaturePending)
    async def pending_handler(request: Request, exc: FeaturePending):
        return JSONResponse(
            status_code=501,
            content=ErrorResponse(
                code="FEATURE_NOT_IMPLEMENTED",
                message=exc.message,
                task_reference=exc.task_reference,
            ).model_dump(),
        )

    app.include_router(router)
    return app


app = create_app()
