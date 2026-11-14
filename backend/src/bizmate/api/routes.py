from fastapi import APIRouter, Depends, HTTPException, Request, status

from bizmate.api.dependencies import (
    current_context,
    require_task_approval,
    require_task_read,
    require_task_write,
)
from bizmate.domain.context import MerchantContext
from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import (
    ApprovalDecisionRequest,
    ClarificationRequest,
    CreateTaskRequest,
    DemoPreview,
    ErrorResponse,
    HealthResponse,
    SessionResponse,
    Task,
    TaskEvent,
    TaskStatus,
    now,
)
from bizmate.persistence.repository import TaskRepository
from bizmate.services.demo import preview
from bizmate.tools.policy import require_approval_engine

router = APIRouter()


def repository(request: Request) -> TaskRepository:
    return request.app.state.tasks


def owned_task(repo: TaskRepository, context: MerchantContext, task_id: str) -> Task:
    task = repo.get_task(context, task_id)
    if task is None or task.merchant_id != context.merchant_id:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    return HealthResponse()


@router.get("/api/v1/session", response_model=SessionResponse, tags=["session"])
def session(context: MerchantContext = Depends(current_context)):
    return SessionResponse(merchant=context.public_merchant(), actor_id=context.actor_id)


@router.get("/api/v1/tasks", response_model=list[Task], tags=["tasks"])
def tasks(
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_read),
):
    return [task for task in repo.list_tasks(context) if task.merchant_id == context.merchant_id]


@router.post(
    "/api/v1/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"]
)
def create_task(
    body: CreateTaskRequest,
    request: Request,
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_write),
):
    result = request.app.state.graph.invoke({"request": body.message})
    task = Task(
        merchant_id=context.merchant_id,
        goal=body.message[:90],
        original_request=body.message,
        next_action="Prepare the request for planning.",
        events=[
            TaskEvent(kind="request_received", message="Your request was saved in demo memory."),
            TaskEvent(kind="scaffold_pending", message=result["next_action"]),
        ],
    )
    task = transition_task(task, TaskStatus.PLANNING, "Prepare the request for planning.")
    task = transition_task(task, TaskStatus(result["status"]), result["next_action"])
    return repo.save(context, task)


@router.get("/api/v1/tasks/{task_id}", response_model=Task, tags=["tasks"])
def task_detail(
    task_id: str,
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_read),
):
    return owned_task(repo, context, task_id)


@router.get("/api/v1/tasks/{task_id}/events", response_model=list[TaskEvent], tags=["tasks"])
def task_events(
    task_id: str,
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_read),
):
    return owned_task(repo, context, task_id).events


@router.post("/api/v1/tasks/{task_id}/messages", response_model=Task, tags=["tasks"])
def add_message(
    task_id: str,
    body: ClarificationRequest,
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_write),
):
    task = owned_task(repo, context, task_id)
    task = task.with_updates(
        events=(*task.events, TaskEvent(kind="merchant_message", message=body.message)),
        updated_at=now(),
    )
    return repo.save(context, task)


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
    context: MerchantContext = Depends(require_task_approval),
):
    owned_task(repo, context, task_id)
    # Both approve/cancel need the real action snapshot/state engine; never report fake success.
    require_approval_engine()


@router.get("/api/v1/demo/preview", response_model=DemoPreview, tags=["demo"])
def demo_preview(context: MerchantContext = Depends(require_task_read)):
    return preview()
