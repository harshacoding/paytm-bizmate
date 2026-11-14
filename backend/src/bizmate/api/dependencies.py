from typing import Annotated

from fastapi import Depends, Request

from bizmate.domain.context import MerchantContext
from bizmate.domain.models import Scope


def current_context(request: Request) -> MerchantContext:
    # Captured at app creation from server configuration, never from headers/body/LLM text.
    return request.app.state.merchant_context


def require_task_read(
    context: Annotated[MerchantContext, Depends(current_context)],
) -> MerchantContext:
    context.require(Scope.TASKS_READ)
    return context


def require_task_write(
    context: Annotated[MerchantContext, Depends(current_context)],
) -> MerchantContext:
    context.require(Scope.TASKS_READ, Scope.TASKS_WRITE)
    return context


def require_task_approval(
    context: Annotated[MerchantContext, Depends(current_context)],
) -> MerchantContext:
    context.require(Scope.TASKS_READ, Scope.TASKS_APPROVE)
    return context
