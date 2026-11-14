from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from bizmate.agents.graph import build_graph
from bizmate.api.routes import router
from bizmate.config import Settings
from bizmate.domain.errors import FeaturePending
from bizmate.domain.models import ErrorResponse, Task, TaskEvent
from bizmate.persistence.repository import TaskConflictError, TaskRepository
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import MERCHANTS


def create_app(settings: Settings | None = None, repo: TaskRepository | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.demo_merchant_id not in MERCHANTS:
        raise ValueError("Unknown synthetic merchant; choose merchant_demo or merchant_other")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if repo is None:
            app.state.tasks = SQLiteTaskRepository(settings.database_file)
            if app.state.tasks.get_task("merchant_demo", "demo-settlement") is None:
                try:
                    app.state.tasks.save(
                        Task(
                            task_id="demo-settlement",
                            merchant_id="merchant_demo",
                            goal="Investigate a short settlement",
                            original_request="Why is my settlement short?",
                            next_action=(
                                "Submit a request to try task intake. Execution is pending BM-07."
                            ),
                            events=[
                                TaskEvent(
                                    kind="demo_seed",
                                    message="Synthetic example; no investigation has run.",
                                )
                            ],
                        )
                    )
                except TaskConflictError:
                    # Another worker seeded the same task while this worker was starting.
                    pass
        yield

    app = FastAPI(
        title="Paytm BizMate API",
        version="0.1.0",
        description="Local prototype with durable SQLite tasks and synthetic fixtures.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    if repo is not None:
        app.state.tasks = repo
    app.state.graph = build_graph()
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

    @app.exception_handler(TaskConflictError)
    async def conflict_handler(request: Request, exc: TaskConflictError):
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(code="TASK_CONFLICT", message=str(exc)).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=ErrorResponse(
                code="NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
                message=str(exc.detail),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        message = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(code="VALIDATION_ERROR", message=message).model_dump(),
        )

    app.include_router(router)
    return app


app = create_app()
