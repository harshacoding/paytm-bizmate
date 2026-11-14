from typing import Annotated

from fastapi import APIRouter, Depends, Request

from bizmate.api.dependencies import current_context
from bizmate.domain.context import MerchantContext
from bizmate.domain.models import ErrorResponse
from bizmate.workflows.campaign import CustomerSegment, SegmentRequest

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["campaigns"],
    responses={
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        503: {"model": ErrorResponse},
    },
)


@router.post("/segment", response_model=CustomerSegment)
def segment(
    body: SegmentRequest,
    request: Request,
    context: Annotated[MerchantContext, Depends(current_context)],
):
    return request.app.state.tools.execute(
        "segment_inactive_customers", context, body.model_dump(mode="json")
    )
