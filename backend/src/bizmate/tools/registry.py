from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from bizmate.domain.errors import FeaturePending
from bizmate.domain.models import Merchant, Model


class ToolMetadata(Model):
    name: str
    description: str
    category: str
    risk: Literal["read", "preparation", "side_effect"]
    required_scopes: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
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

    def discover(self, merchant: Merchant) -> list[ToolMetadata]:
        return [
            m.model_copy(deep=True)
            for m, _, _ in self._tools.values()
            if set(m.required_scopes) <= set(merchant.scopes)
        ]

    def execute(self, name: str, merchant: Merchant, inputs: dict[str, Any]) -> Any:
        metadata, schema, handler = self._tools[name]
        if not set(metadata.required_scopes) <= set(merchant.scopes):
            raise PermissionError("Missing tool scope")
        parsed = schema.model_validate(inputs)
        # Preconditions and write approvals must be enforced before adding any write handler.
        if metadata.risk != "read" or metadata.approval_required or metadata.preconditions:
            raise FeaturePending("BM-06", "Consequential tool execution is not implemented.")
        return handler(merchant, parsed)
