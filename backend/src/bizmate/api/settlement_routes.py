from typing import Annotated

from fastapi import APIRouter, Depends, Request

from bizmate.api.dependencies import current_context
from bizmate.domain.context import MerchantContext
from bizmate.domain.models import ErrorResponse
from bizmate.workflows.settlement import ReconciliationRequest, SettlementProof

router = APIRouter(
    prefix="/api/v1/settlements",
    tags=["settlements"],
    responses={
        403: {"model": ErrorResponse},
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
