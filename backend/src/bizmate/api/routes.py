from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from bizmate.api.dependencies import (
    current_context,
    require_task_approval,
    require_task_read,
    require_task_write,
)
from bizmate.domain.chat import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    CreateConversationRequest,
    SendConversationMessageRequest,
    UpdateConversationLanguageRequest,
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
    new_id,
    now,
)
from bizmate.persistence.conversations import ConversationConflictError, ConversationRepository
from bizmate.persistence.repository import TaskRepository
from bizmate.persistence.sqlite import SQLiteTaskRepository
from bizmate.services.demo import preview
from bizmate.tools.policy import require_approval_engine

router = APIRouter(
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
    }
)


def conversation_repository(request: Request) -> ConversationRepository:
    return request.app.state.conversations


def owned_conversation(
    repo: ConversationRepository, context: MerchantContext, conversation_id: str
):
    conversation = repo.get(context, conversation_id)
    if conversation is None or conversation.merchant_id != context.merchant_id:
        raise HTTPException(404, "Conversation not found")
    return conversation


def repository(request: Request) -> TaskRepository:
    return request.app.state.tasks


def owned_task(repo: TaskRepository, context: MerchantContext, task_id: str) -> Task:
    task = repo.get_task(context, task_id)
    if task is None or task.merchant_id != context.merchant_id:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(repo: TaskRepository = Depends(repository)):
    return HealthResponse(storage="sqlite" if isinstance(repo, SQLiteTaskRepository) else "memory")


@router.get("/api/v1/session", response_model=SessionResponse, tags=["session"])
def session(context: MerchantContext = Depends(current_context)):
    return SessionResponse(merchant=context.public_merchant(), actor_id=context.actor_id)


@router.get("/api/v1/tasks", response_model=list[Task], tags=["tasks"])
def tasks(
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_read),
    conversation_id: str | None = Query(default=None, min_length=1),
):
    return [
        task
        for task in repo.list_tasks(context)
        if task.merchant_id == context.merchant_id
        and (conversation_id is None or task.conversation_id == conversation_id)
    ]


@router.post(
    "/api/v1/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"]
)
def create_task(
    body: CreateTaskRequest,
    request: Request,
    repo: TaskRepository = Depends(repository),
    context: MerchantContext = Depends(require_task_write),
):
    if body.conversation_id is not None:
        owned_conversation(request.app.state.conversations, context, body.conversation_id)
    result = request.app.state.graph.invoke({"request": body.message})
    task = Task(
        merchant_id=context.merchant_id,
        conversation_id=body.conversation_id,
        # Normalize only the display title, not the original request.
        goal=body.message.strip()[:90],
        original_request=body.message,
        next_action="Prepare the request for planning.",
        events=[
            TaskEvent(kind="request_received", message="Your request was saved."),
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


@router.post(
    "/api/v1/conversations",
    response_model=Conversation,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def create_conversation(
    body: CreateConversationRequest,
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_write),
):
    return repo.create(context, body.title, body.preferred_language or context.preferred_language)


@router.get("/api/v1/conversations", response_model=list[Conversation], tags=["conversations"])
def conversations(
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_read),
):
    return repo.list_conversations(context)


@router.get(
    "/api/v1/conversations/{conversation_id}", response_model=Conversation, tags=["conversations"]
)
def conversation_detail(
    conversation_id: str,
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_read),
):
    return owned_conversation(repo, context, conversation_id)


@router.patch(
    "/api/v1/conversations/{conversation_id}", response_model=Conversation, tags=["conversations"]
)
def update_conversation_language(
    conversation_id: str,
    body: UpdateConversationLanguageRequest,
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_write),
):
    try:
        return repo.set_preferred_language(context, conversation_id, body.preferred_language)
    except KeyError as exc:
        raise HTTPException(404, "Conversation not found") from exc


@router.get(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessage],
    tags=["conversations"],
)
def conversation_messages(
    conversation_id: str,
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_read),
):
    messages = repo.messages(context, conversation_id)
    if messages is None:
        raise HTTPException(404, "Conversation not found")
    return messages


@router.post(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=ConversationTurn,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
def send_conversation_message(
    conversation_id: str,
    body: SendConversationMessageRequest,
    request: Request,
    repo: ConversationRepository = Depends(conversation_repository),
    context: MerchantContext = Depends(require_task_write),
):
    owned_conversation(repo, context, conversation_id)
    client_message_id = body.client_message_id or new_id()
    previous = repo.get_turn(context, conversation_id, client_message_id)
    if previous is not None:
        if previous.user_message.content != body.content or (
            body.language is not None and previous.user_message.language != body.language
        ):
            raise ConversationConflictError("Client message ID was used with different content")
        return previous
    # Chat invokes the scaffold response without conversation IDs as task/checkpoint thread IDs.
    # Business tasks remain separately persisted through the task API and repository.
    result = request.app.state.graph.invoke({"request": body.content})
    try:
        return repo.save_turn(
            context,
            conversation_id,
            body.content,
            result["next_action"],
            client_message_id,
            user_language=body.language,
            assistant_language=result.get("response_language") or "en",
            detected_language=result.get("detected_language"),
        )
    except KeyError as exc:
        raise HTTPException(404, "Conversation not found") from exc
