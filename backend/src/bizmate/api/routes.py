from fastapi import APIRouter, Depends, HTTPException, Request, status

from bizmate.domain.models import (
    ApprovalDecisionRequest,
    ClarificationRequest,
    CreateTaskRequest,
    DemoPreview,
    ErrorResponse,
    HealthResponse,
    Merchant,
    SessionResponse,
    Task,
    TaskEvent,
    TaskStatus,
    now,
)
from bizmate.persistence.repository import TaskRepository
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import MERCHANTS, preview
from bizmate.tools.policy import require_approval_engine

router = APIRouter(
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
    }
)


def current_merchant(request: Request) -> Merchant:
    # Local-only synthetic identity: NO caller-provided header/query/body override.
    return MERCHANTS[request.app.state.settings.demo_merchant_id].model_copy(deep=True)


def repository(request: Request) -> TaskRepository:
    return request.app.state.tasks


def owned_task(repo: TaskRepository, merchant: Merchant, task_id: str) -> Task:
    task = repo.get_task(merchant.merchant_id, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(repo: TaskRepository = Depends(repository)):
    return HealthResponse(storage="sqlite" if isinstance(repo, SQLiteTaskRepository) else "memory")


@router.get("/api/v1/session", response_model=SessionResponse, tags=["session"])
def session(merchant: Merchant = Depends(current_merchant)):
    return SessionResponse(merchant=merchant)


@router.get("/api/v1/tasks", response_model=list[Task], tags=["tasks"])
def tasks(
    repo: TaskRepository = Depends(repository), merchant: Merchant = Depends(current_merchant)
):
    return repo.list_tasks(merchant.merchant_id)


@router.post(
    "/api/v1/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"]
)
def create_task(
    body: CreateTaskRequest,
    request: Request,
    repo: TaskRepository = Depends(repository),
    merchant: Merchant = Depends(current_merchant),
):
    result = request.app.state.graph.invoke({"request": body.message})
    task = Task(
        merchant_id=merchant.merchant_id,
        goal=body.message[:90],
        original_request=body.message,
        status=TaskStatus(result["status"]),
        next_action=result["next_action"],
        events=[
            TaskEvent(kind="request_received", message="Your request was saved."),
            TaskEvent(kind="scaffold_pending", message=result["next_action"]),
        ],
    )
    return repo.save(task)


@router.get("/api/v1/tasks/{task_id}", response_model=Task, tags=["tasks"])
def task_detail(
    task_id: str,
    repo: TaskRepository = Depends(repository),
    merchant: Merchant = Depends(current_merchant),
):
    return owned_task(repo, merchant, task_id)


@router.get("/api/v1/tasks/{task_id}/events", response_model=list[TaskEvent], tags=["tasks"])
def task_events(
    task_id: str,
    repo: TaskRepository = Depends(repository),
    merchant: Merchant = Depends(current_merchant),
):
    return owned_task(repo, merchant, task_id).events


@router.post("/api/v1/tasks/{task_id}/messages", response_model=Task, tags=["tasks"])
def add_message(
    task_id: str,
    body: ClarificationRequest,
    repo: TaskRepository = Depends(repository),
    merchant: Merchant = Depends(current_merchant),
):
    task = owned_task(repo, merchant, task_id)
    task.events.append(TaskEvent(kind="merchant_message", message=body.message))
    task.updated_at = now()
    return repo.save(task)


@router.post(
    "/api/v1/tasks/{task_id}/approvals/{approval_id}",
    response_model=ErrorResponse,
    responses={501: {"model": ErrorResponse}},
    tags=["approvals"],
)
def decide_approval(
    task_id: str,
    approval_id: str,
    body: ApprovalDecisionRequest,
    repo: TaskRepository = Depends(repository),
    merchant: Merchant = Depends(current_merchant),
):
    owned_task(repo, merchant, task_id)
    # Both approve/cancel need the real action snapshot/state engine; never report fake success.
    require_approval_engine()


@router.get("/api/v1/demo/preview", response_model=DemoPreview, tags=["demo"])
def demo_preview(merchant: Merchant = Depends(current_merchant)):
    return preview()
