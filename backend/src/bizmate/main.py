from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from bizmate.agents.graph import build_graph
from bizmate.api.campaign_routes import router as campaign_router
from bizmate.api.mock_routes import router as mock_router
from bizmate.api.routes import router
from bizmate.api.schema import install_domain_schemas
from bizmate.config import Settings
from bizmate.domain.errors import AccessDenied, FeaturePending
from bizmate.domain.models import ErrorResponse, Task, TaskEvent
from bizmate.persistence.conversations import (
    ConversationConflictError,
    ConversationRepository,
    SQLiteConversationRepository,
)
from bizmate.persistence.repository import TaskConflictError, TaskRepository
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.services.mock_store import MockTimeout, SQLiteMockStore
from bizmate.services.mocks import MockServices
from bizmate.tools.campaign_tools import register_campaign_tools
from bizmate.tools.mock_tools import register_mock_tools
from bizmate.tools.policy import ActionNotFound
from bizmate.tools.registry import PreconditionFailed, ToolRegistry, UnknownTool


def create_app(
    settings: Settings | None = None,
    repo: TaskRepository | None = None,
    chat_repo: ConversationRepository | None = None,
    tools: ToolRegistry | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if settings.demo_merchant_id not in MERCHANTS:
        raise ValueError("Unknown synthetic merchant; choose merchant_demo or merchant_other")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if chat_repo is None:
            app.state.conversations = SQLiteConversationRepository(settings.database_file)
        if repo is None:
            app.state.tasks = SQLiteTaskRepository(settings.database_file)
            if app.state.tasks.get_task(demo_context("merchant_demo"), "demo-settlement") is None:
                try:
                    app.state.tasks.save(
                        demo_context("merchant_demo"),
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
                        ),
                    )
                except TaskConflictError:
                    # Another worker seeded the same task while this worker was starting.
                    pass
        app.state.mock_services = MockServices(
            SQLiteMockStore(settings.database_file),
            app.state.tasks,
            controls_enabled=settings.demo_controls_enabled,
        )
        if tools is None:
            register_mock_tools(app.state.tools, app.state.mock_services)
            register_campaign_tools(app.state.tools, app.state.mock_services)
        yield

    app = FastAPI(
        title="Paytm BizMate API",
        version="0.4.0",
        description="Local prototype with durable SQLite tasks and synthetic fixtures.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.merchant_context = demo_context(settings.demo_merchant_id)
    if repo is not None:
        app.state.tasks = repo
    if chat_repo is not None:
        app.state.conversations = chat_repo
    app.state.graph = build_graph()
    app.state.tools = tools if tools is not None else ToolRegistry()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
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

    @app.exception_handler(ConversationConflictError)
    async def message_conflict_handler(request: Request, exc: ConversationConflictError):
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(code="MESSAGE_CONFLICT", message=str(exc)).model_dump(),
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

    @app.exception_handler(AccessDenied)
    async def access_denied_handler(request: Request, exc: AccessDenied):
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(code="ACCESS_DENIED", message=str(exc)).model_dump(),
        )

    @app.exception_handler(MockTimeout)
    async def mock_timeout_handler(request: Request, exc: MockTimeout):
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(code="MOCK_TIMEOUT", message=str(exc)).model_dump(),
        )

    @app.exception_handler(ActionNotFound)
    @app.exception_handler(UnknownTool)
    async def action_not_found(request: Request, exc: Exception):
        return JSONResponse(
            status_code=404, content=ErrorResponse(code="NOT_FOUND", message=str(exc)).model_dump()
        )

    @app.exception_handler(PreconditionFailed)
    async def precondition_failed(request: Request, exc: PreconditionFailed):
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(code="PRECONDITION_FAILED", message=str(exc)).model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def tool_validation_failed(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="VALIDATION_ERROR", message="Action inputs failed validation."
            ).model_dump(),
        )

    app.include_router(router)
    app.include_router(mock_router)
    app.include_router(campaign_router)
    install_domain_schemas(app)
    return app


app = create_app()
