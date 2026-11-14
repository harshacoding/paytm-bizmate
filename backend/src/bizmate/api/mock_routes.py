from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from bizmate.api.dependencies import current_context
from bizmate.domain.context import MerchantContext
from bizmate.domain.models import ErrorResponse
from bizmate.services.mock_models import (
    ClockAdvance,
    ClockState,
    ConsentControl,
    CustomerHistory,
    CustomerRecord,
    FailureControl,
    SettlementReport,
)
from bizmate.services.mocks import MockServices

router = APIRouter(
    prefix="/api/v1/demo",
    tags=["synthetic services"],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        503: {"model": ErrorResponse},
    },
)


def services(request: Request) -> MockServices:
    return request.app.state.mock_services


Context = Annotated[MerchantContext, Depends(current_context)]
Services = Annotated[MockServices, Depends(services)]


@router.get("/settlement", response_model=SettlementReport)
def settlement(context: Context, providers: Services):
    return providers.report(context)


@router.get("/customers", response_model=CustomerHistory)
def customers(context: Context, providers: Services):
    return providers.customers(context)


@router.get("/clock", response_model=ClockState)
def clock(context: Context, providers: Services):
    return ClockState(current_time=providers.clock(context))


@router.post("/clock/advance", response_model=ClockState)
def advance(body: ClockAdvance, context: Context, providers: Services):
    try:
        return ClockState(current_time=providers.advance(context, body.seconds))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/reset", response_model=ClockState)
def reset(context: Context, providers: Services):
    return ClockState(current_time=providers.reset(context))


@router.post("/failures", response_model=FailureControl)
def failure(body: FailureControl, context: Context, providers: Services):
    providers.inject_failure(context, body)
    return body


@router.patch("/customers/{customer_id}/consent", response_model=CustomerRecord)
def consent(customer_id: str, body: ConsentControl, context: Context, providers: Services):
    try:
        return providers.set_consent(context, customer_id, body.marketing_consent)
    except KeyError as exc:
        raise HTTPException(404, "Customer not found") from exc
