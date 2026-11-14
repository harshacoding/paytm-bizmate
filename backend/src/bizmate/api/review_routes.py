from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from bizmate.api.dependencies import require_task_read, require_task_write
from bizmate.api.routes import orchestrator, owned_task
from bizmate.domain.context import MerchantContext
from bizmate.domain.models import ErrorResponse, Intent, Task, TaskStatus
from bizmate.workflows.review import CampaignEdit, CampaignReview, HandoffDraft, HandoffReview

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["campaign and handoff review"],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
ReadContext = Annotated[MerchantContext, Depends(require_task_read)]
WriteContext = Annotated[MerchantContext, Depends(require_task_write)]


def campaign_review(task):
    if task.intent != Intent.WIN_BACK:
        raise HTTPException(404, "Campaign review not found")
    data = task.workflow_data
    segment = data.get("segment", {})
    approval = task.approvals[-1] if task.approvals else None
    if approval and approval.decision == "cancelled":
        approval = None
    receipt = task.receipts[-1] if task.receipts else None
    verification = task.verifications[-1] if task.verifications else None
    delivery = data.get("verification_result")
    return CampaignReview(
        task_id=task.task_id,
        merchant_id=task.merchant_id,
        revision=task.revision,
        message=data.get("extraction", {}).get("offer_message"),
        inactivity_days=data.get("extraction", {}).get("inactivity_days", 30),
        recipient_ids=segment.get("recipient_ids", []),
        eligible_count=segment.get("eligible_count"),
        estimated_cost_paise=segment.get("estimated_cost_paise"),
        approval=approval,
        receipt=receipt,
        verification=verification,
        delivery=delivery if verification and verification.verified else None,
        editable=(
            task.status
            in {
                TaskStatus.AWAITING_INPUT,
                TaskStatus.AWAITING_APPROVAL,
                TaskStatus.READY,
                TaskStatus.PLANNING,
            }
            and not task.receipts
            and not task.has_unresolved_execution
        ),
    )


@router.get("/{task_id}/campaign", response_model=CampaignReview)
def get_campaign(task_id: str, request: Request, context: ReadContext):
    return campaign_review(owned_task(request.app.state.tasks, context, task_id))


@router.patch("/{task_id}/campaign", response_model=Task)
def edit_campaign(task_id: str, body: CampaignEdit, request: Request, context: WriteContext):
    owned_task(request.app.state.tasks, context, task_id)
    return orchestrator(request).run(context, task_id, campaign_edit=body)


@router.get("/{task_id}/handoff", response_model=HandoffReview)
def get_handoff(task_id: str, request: Request, context: ReadContext):
    task = owned_task(request.app.state.tasks, context, task_id)
    if "handoff_draft" not in task.workflow_data:
        raise HTTPException(404, "Handoff review not found")
    receipt = task.receipts[-1] if task.receipts else None
    verification = task.verifications[-1] if task.verifications else None
    approval = task.approvals[-1] if task.approvals else None
    routing = (
        "verified"
        if verification and verification.verified
        else "unverified"
        if receipt or task.has_unresolved_execution
        else "awaiting_approval"
        if approval and approval.decision == "pending"
        else "approved"
        if approval and approval.decision == "approved"
        else "cancelled"
        if approval and approval.decision == "cancelled"
        else "unavailable"
    )
    return HandoffReview(
        task_id=task.task_id,
        merchant_id=task.merchant_id,
        revision=task.revision,
        draft=HandoffDraft.model_validate(task.workflow_data["handoff_draft"]),
        explanation=task.workflow_data["handoff_explanation"],
        gaps=task.capability_gaps,
        approval=approval,
        receipt=receipt,
        verification=verification,
        routing_status=routing,
    )
