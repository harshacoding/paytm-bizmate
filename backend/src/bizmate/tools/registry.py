"""Backend-owned tool definitions. Model output can select tools, never register them."""

import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self, TypeVar

from pydantic import Field, JsonValue, StrictBool, ValidationError, model_validator

from bizmate.domain.context import MerchantContext, require_context
from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Intent, Model, Scope
from bizmate.domain.types import Identifier, ShortText, Text

IDENTITY_FIELDS = frozenset({"merchant_id", "actor_id", "scopes", "merchant_context", "session"})
Input = TypeVar("Input", bound=Model)
Output = TypeVar("Output", bound=Model)
Precondition = Callable[[MerchantContext, Any], bool]


class UnknownTool(LookupError):
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Unknown tool: {tool_name}")


class PreconditionFailed(ValueError):
    def __init__(self, tool_name: str, precondition: str):
        self.tool_name = tool_name
        self.precondition = precondition
        super().__init__(f"Tool precondition failed: {tool_name}/{precondition}")


class InvalidToolOutput(ValueError):
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool returned an invalid result: {tool_name}")


class VerificationSpec(Model):
    tool_name: Identifier
    description: Text


class ToolMetadata(Model):
    name: Identifier
    description: Text
    category: ShortText
    intents: frozenset[Intent] = Field(min_length=1)
    risk: Literal["read", "preparation", "side_effect"]
    required_scopes: frozenset[Scope] = Field(min_length=1)
    preconditions: tuple[Identifier, ...] = ()
    approval_required: StrictBool = False
    idempotency: Literal["safe_retry", "none", "key_required"] = "safe_retry"
    verification: VerificationSpec | None = None

    @model_validator(mode="after")
    def consistent_policy(self) -> Self:
        if Intent.UNKNOWN in self.intents:
            raise ValueError("Tools must target a supported intent")
        if len(set(self.preconditions)) != len(self.preconditions):
            raise ValueError("Duplicate preconditions")
        if self.risk == "side_effect":
            if not self.approval_required or self.idempotency != "key_required":
                raise ValueError("Side effects require approval and an idempotency key")
            if self.verification is None or self.verification.tool_name == self.name:
                raise ValueError("Side effects require a separate verification read")
            if not self.required_scopes & {
                Scope.TASKS_WRITE,
                Scope.TICKETS_WRITE,
                Scope.CAMPAIGNS_WRITE,
            }:
                raise ValueError("Side effects require a write scope")
        elif self.approval_required or self.idempotency == "key_required" or self.verification:
            raise ValueError("Approval, keyed writes and verification belong to side effects")
        return self


class ToolDescriptor(Model):
    metadata: ToolMetadata
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    handler_reference: str
    execution_gate: Literal["available", "approval_required"]


@dataclass(frozen=True)
class _Definition:
    metadata: ToolMetadata
    input_schema: type[Model]
    output_schema: type[Model]
    handler: Callable
    preconditions: tuple[tuple[str, Precondition], ...]


def _require_schema(schema: type[Model]) -> None:
    if (
        not isinstance(schema, type)
        or not issubclass(schema, Model)
        or schema.model_config.get("extra") != "forbid"
        or not schema.model_config.get("frozen")
        or schema.model_config.get("revalidate_instances") != "always"
    ):
        raise TypeError("Tool schemas must be frozen, revalidated, extra-forbid domain Models")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, _Definition] = {}

    def register(
        self,
        metadata: ToolMetadata,
        input_schema: type[Input],
        handler: Callable[[MerchantContext, Input], Output | dict[str, Any]],
        *,
        output_schema: type[Output],
        preconditions: Mapping[str, Precondition] | None = None,
    ) -> None:
        # Revalidate even model_construct/model_copy input at this backend boundary.
        metadata = ToolMetadata.model_validate(metadata.model_dump()).model_copy(deep=True)
        if metadata.name in self._tools:
            raise ValueError("Duplicate tool registration")
        _require_schema(input_schema)
        _require_schema(output_schema)
        predicates = dict(preconditions or {})
        if set(predicates) != set(metadata.preconditions):
            raise ValueError("Every declared precondition needs exactly one backend predicate")
        for callback in (handler, *predicates.values()):
            if (
                not callable(callback)
                or inspect.iscoroutinefunction(callback)
                or inspect.iscoroutinefunction(type(callback).__call__)
            ):
                raise TypeError("Tool handlers and predicates must be synchronous callables")
        if metadata.verification:
            verifier = self._tools.get(metadata.verification.tool_name)
            if (
                verifier is None
                or verifier.metadata.risk != "read"
                or verifier.metadata.idempotency != "safe_retry"
                or not metadata.intents <= verifier.metadata.intents
            ):
                raise ValueError(
                    "Register a safe, relevant verification read before its write tool"
                )
        self._tools[metadata.name] = _Definition(
            metadata,
            input_schema,
            output_schema,
            handler,
            tuple((name, predicates[name]) for name in metadata.preconditions),
        )

    def _required_scopes(self, definition: _Definition) -> frozenset[Scope]:
        scopes = definition.metadata.required_scopes
        if definition.metadata.verification:
            scopes |= self._tools[
                definition.metadata.verification.tool_name
            ].metadata.required_scopes
        return scopes

    def discover(self, context: MerchantContext, *, intent: Intent) -> list[ToolDescriptor]:
        """Relevant permitted capabilities. Does not run predicates or grant approval."""
        require_context(context)
        intent = Intent(intent)
        return [
            ToolDescriptor(
                metadata=definition.metadata.model_copy(deep=True),
                input_schema=definition.input_schema.model_json_schema(),
                output_schema=definition.output_schema.model_json_schema(mode="serialization"),
                handler_reference=(
                    f"{definition.handler.__module__}."
                    + getattr(definition.handler, "__qualname__", type(definition.handler).__name__)
                ),
                execution_gate=(
                    "approval_required"
                    if definition.metadata.risk == "side_effect"
                    else "available"
                ),
            )
            for _, definition in sorted(self._tools.items())
            if intent in definition.metadata.intents
            and self._required_scopes(definition) <= context.scopes
        ]

    def _prepare(
        self,
        name: str,
        context: MerchantContext,
        inputs: dict[str, JsonValue],
    ) -> tuple[_Definition, Model]:
        require_context(context)
        definition = self._tools.get(name)
        if definition is None:
            raise UnknownTool(name)
        context.require(*self._required_scopes(definition))
        if not isinstance(inputs, dict) or any(not isinstance(key, str) for key in inputs):
            raise ValueError("Tool inputs must be a JSON object")
        if IDENTITY_FIELDS & inputs.keys():
            raise AccessDenied("Tool inputs cannot supply identity or permissions")
        # JSON strict mode permits dates/enums on the wire, without coercing money or booleans.
        snapshot = json.dumps(inputs, allow_nan=False)
        parsed = definition.input_schema.model_validate_json(snapshot, strict=True)
        return definition, parsed

    def _check_preconditions(self, definition, context, parsed):
        for precondition, check in definition.preconditions:
            # A predicate cannot mutate the validated input subsequently sent to a handler.
            if check(context, parsed.model_copy(deep=True)) is not True:
                raise PreconditionFailed(definition.metadata.name, precondition)

    def execute(self, name: str, context: MerchantContext, inputs: dict[str, JsonValue]) -> Model:
        definition, parsed = self._prepare(name, context, inputs)
        if definition.metadata.risk == "side_effect":
            raise AccessDenied("Side effects must execute through the approval engine")
        self._check_preconditions(definition, context, parsed)
        result = definition.handler(context, parsed)
        return self._result(definition, context, result)

    def _result(self, definition, context, result):
        try:
            output = definition.output_schema.model_validate(result, strict=True)
        except ValidationError as exc:
            raise InvalidToolOutput(definition.metadata.name) from exc
        if "merchant_id" in type(output).model_fields:
            context.require_owner(output.merchant_id)
        return output.model_copy(deep=True)
