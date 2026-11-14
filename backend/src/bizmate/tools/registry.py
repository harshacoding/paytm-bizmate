from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.errors import AccessDenied, FeaturePending
from bizmate.domain.models import Model, Scope


class ToolMetadata(Model):
    name: str
    description: str
    category: str
    risk: Literal["read", "preparation", "side_effect"]
    required_scopes: frozenset[Scope] = frozenset()
    preconditions: tuple[str, ...] = ()
    approval_required: bool = False
    idempotency: str = "none"
    verification_tool: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolMetadata, type[BaseModel], Callable]] = {}

    def register(self, metadata: ToolMetadata, schema: type[BaseModel], handler: Callable) -> None:
        if metadata.name in self._tools:
            raise ValueError("Duplicate tool registration")
        self._tools[metadata.name] = (metadata, schema, handler)

    def discover(self, context: MerchantContext) -> list[ToolMetadata]:
        require_context(context)
        return [
            m.model_copy(deep=True)
            for m, _, _ in self._tools.values()
            if m.required_scopes <= context.scopes
        ]

    def execute(self, name: str, context: MerchantContext, inputs: dict[str, Any]) -> Any:
        require_context(context)
        metadata, schema, handler = self._tools[name]
        context.require(*metadata.required_scopes)
        parsed = schema.model_validate(inputs)
        if {"merchant_id", "actor_id", "scopes", "merchant_context", "session"} & inputs.keys():
            raise AccessDenied("Tool inputs cannot supply identity or permissions")
        # Preconditions and write approvals must be enforced before adding any write handler.
        if metadata.risk != "read" or metadata.approval_required or metadata.preconditions:
            raise FeaturePending("BM-06", "Consequential tool execution is not implemented.")
        return handler(context, parsed)
