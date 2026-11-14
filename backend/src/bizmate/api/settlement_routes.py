from typing import Annotated

from fastapi import APIRouter, Depends, Request

from bizmate.api.dependencies import current_context
from bizmate.api.routes import orchestrator, owned_conversation
from bizmate.domain.context import MerchantContext
from bizmate.domain.models import ErrorResponse, Task
from bizmate.services.scheduler import run_due_tasks
from bizmate.workflows.investigation import InvestigationRequest, InvestigationView
from bizmate.workflows.settlement import ReconciliationRequest, SettlementProof

router = APIRouter(
    prefix="/api/v1/settlements",
    tags=["settlements"],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        503: {"model": ErrorResponse},
    },
)


@router.post("/reconcile", response_model=SettlementProof)
def reconcile(
    body: ReconciliationRequest,
    request: Request,
    context: Annotated[MerchantContext, Depends(current_context)],
):
    return request.app.state.tools.execute(
        "reconcile_settlement", context, body.model_dump(mode="json")
    )


Context = Annotated[MerchantContext, Depends(current_context)]


@router.post("/investigations", response_model=InvestigationView, status_code=201)
def investigate(body: InvestigationRequest, request: Request, context: Context):
    if body.conversation_id:
        owned_conversation(request.app.state.conversations, context, body.conversation_id)
    workflow = request.app.state.settlements
    task = workflow.start(context, body)
    return workflow.view(context, task.task_id)


@router.get("/investigations/{task_id}", response_model=InvestigationView)
def investigation(task_id: str, request: Request, context: Context):
    return request.app.state.settlements.view(context, task_id)


@router.post("/investigations/{task_id}/resume", response_model=InvestigationView)
def resume_investigation(task_id: str, request: Request, context: Context):
    workflow = request.app.state.settlements
    if workflow.get(context, task_id).workflow_data.get("engine_version") == 1:
        orchestrator(request).run(context, task_id)
    else:
        workflow.resume(context, task_id)
    return workflow.view(context, task_id)


@router.post("/scan", response_model=list[InvestigationView])
def scan(request: Request, context: Context):
    workflow = request.app.state.settlements
    return [workflow.view(context, task.task_id) for task in workflow.scan(context)]


@router.post("/run-due", response_model=list[Task])
def run_due(request: Request, context: Context):
    return run_due_tasks(request.app.state.settlements, context)
