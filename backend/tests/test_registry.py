from datetime import date

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Intent, Model, Scope, Task
from bizmate.domain.types import Identifier, MessageText, Money
from bizmate.persistence.repository import MemoryTaskRepository
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.tools.registry import (
    InvalidToolOutput,
    PreconditionFailed,
    ToolMetadata,
    ToolRegistry,
    UnknownTool,
    VerificationSpec,
)


class Inputs(Model):
    reference: Identifier
    amount_paise: Money = 0
    message: MessageText = "Original message"


class Result(Model):
    merchant_id: Identifier
    reference: Identifier
    amount_paise: Money = 0
    message: MessageText = "Original message"


def read_metadata(**changes):
    return ToolMetadata(
        **{
            "name": "get_transactions",
            "description": "Read synthetic transactions for the current merchant",
            "category": "settlement",
            "intents": [Intent.SETTLEMENT],
            "risk": "read",
            "required_scopes": [Scope.PAYMENTS_READ],
            **changes,
        }
    )


def write_metadata(**changes):
    return read_metadata(
        **{
            "name": "create_support_ticket",
            "risk": "side_effect",
            "required_scopes": [Scope.TICKETS_WRITE],
            "approval_required": True,
            "idempotency": "key_required",
            "verification": VerificationSpec(
                tool_name="get_ticket_status", description="Read the stored ticket independently"
            ),
            **changes,
        }
    )


def handler(context, inputs):
    return Result(merchant_id=context.merchant_id, **inputs.model_dump())


def register_read(registry, metadata=None, callback=handler, **kwargs):
    registry.register(metadata or read_metadata(), Inputs, callback, output_schema=Result, **kwargs)


def register_write(registry, callback=handler, **changes):
    register_read(
        registry,
        read_metadata(name="get_ticket_status", required_scopes=[Scope.TASKS_READ]),
    )
    registry.register(write_metadata(**changes), Inputs, callback, output_schema=Result)


@pytest.fixture
def registry():
    registry = ToolRegistry()
    register_read(registry)
    return registry


def test_typed_dispatch_injects_server_context_and_preserves_message(registry):
    original = "  తెలుగు हिंदी original\n"
    result = registry.execute(
        "get_transactions",
        demo_context("merchant_demo"),
        {"reference": "source-1", "amount_paise": 16680, "message": original},
    )
    assert isinstance(result, Result)
    assert result == Result(
        merchant_id="merchant_demo", reference="source-1", amount_paise=16680, message=original
    )


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"reference": 123},
        {"reference": "bad reference"},
        {"reference": "r", "extra": "ignored?"},
        {"reference": "r", "amount_paise": "16680"},
        {"reference": "r", "amount_paise": 16680.0},
        {"reference": "r", "amount_paise": True},
        {"reference": "r", "amount_paise": -1},
        {"reference": "r", "amount_paise": 9007199254740992},
        {"reference": "r", "message": "   "},
    ],
)
def test_invalid_inputs_never_reach_handler(inputs):
    calls = []
    registry = ToolRegistry()
    register_read(registry, callback=lambda *args: calls.append(True))
    with pytest.raises(ValidationError):
        registry.execute("get_transactions", demo_context("merchant_demo"), inputs)
    assert calls == []


@pytest.mark.parametrize(
    "inputs",
    [
        [],
        "payload",
        None,
        {1: "bad"},
        {"reference": "r", "amount_paise": float("nan")},
        {"reference": "r", "amount_paise": object()},
    ],
)
def test_non_json_inputs_are_rejected(registry, inputs):
    with pytest.raises((ValueError, TypeError)):
        registry.execute("get_transactions", demo_context("merchant_demo"), inputs)


@pytest.mark.parametrize(
    "identity",
    [
        "merchant_id",
        "actor_id",
        "scopes",
        "merchant_context",
        "session",
    ],
)
def test_arguments_cannot_supply_authority_even_if_schema_accepts_it(identity):
    class SpoofedInputs(Inputs):
        merchant_id: str | None = None
        actor_id: str | None = None
        scopes: list[str] = []
        merchant_context: dict | None = None
        session: str | None = None

    registry = ToolRegistry()
    calls = []
    registry.register(
        read_metadata(), SpoofedInputs, lambda *a: calls.append(True), output_schema=Result
    )
    with pytest.raises(AccessDenied):
        registry.execute(
            "get_transactions",
            demo_context("merchant_demo"),
            {"reference": "r", identity: "untrusted"},
        )
    assert calls == []


@pytest.mark.parametrize(
    "tool",
    ["nonexistent", "change_bank_account", "transfer_money", "issue_refund", "send_real_payment"],
)
def test_unknown_and_unsupported_tools_cannot_execute(registry, tool):
    with pytest.raises(UnknownTool) as exc:
        registry.execute(tool, demo_context("merchant_demo"), {"reference": "r"})
    assert exc.value.tool_name == tool


def test_discovery_filters_intent_and_scope_and_includes_typed_metadata(registry):
    register_read(
        registry,
        read_metadata(
            name="get_customers_and_orders",
            category="crm",
            intents=[Intent.WIN_BACK],
            required_scopes=[Scope.CUSTOMERS_READ],
        ),
    )
    context = demo_context("merchant_demo")
    tools = registry.discover(context, intent=Intent.SETTLEMENT)
    assert [tool.metadata.name for tool in tools] == ["get_transactions"]
    assert tools[0].input_schema["additionalProperties"] is False
    assert tools[0].input_schema["required"] == ["reference"]
    assert "merchant_id" in tools[0].output_schema["properties"]
    assert tools[0].handler_reference == f"{handler.__module__}.{handler.__qualname__}"
    assert tools[0].execution_gate == "available"
    assert [tool.metadata.name for tool in registry.discover(context, intent=Intent.WIN_BACK)] == [
        "get_customers_and_orders"
    ]
    assert registry.discover(demo_context("merchant_other"), intent=Intent.WIN_BACK) == []
    assert registry.discover(context, intent=Intent.UNKNOWN) == []
    # Serializes to planner-safe JSON; no callable objects are exposed.
    assert '"input_schema"' in tools[0].model_dump_json()


def test_discovery_does_not_leak_mutable_schemas_or_run_preconditions():
    registry = ToolRegistry()
    calls = []
    register_read(
        registry,
        read_metadata(preconditions=["ready"]),
        preconditions={"ready": lambda *a: calls.append(True)},
    )
    descriptor = registry.discover(demo_context("merchant_demo"), intent=Intent.SETTLEMENT)[0]
    descriptor.input_schema["properties"]["reference"]["type"] = "integer"
    again = registry.discover(demo_context("merchant_demo"), intent=Intent.SETTLEMENT)[0]
    assert again.input_schema["properties"]["reference"]["type"] == "string"
    assert calls == []


def test_scopes_are_rechecked_at_execution_and_only_trusted_context_is_accepted():
    registry = ToolRegistry()
    calls = []
    register_read(
        registry,
        read_metadata(required_scopes=[Scope.CUSTOMERS_READ]),
        callback=lambda *a: calls.append(True),
    )
    assert registry.discover(demo_context("merchant_demo"), intent=Intent.SETTLEMENT)
    for context in (
        demo_context("merchant_other"),
        MERCHANTS["merchant_demo"],
        {"merchant_id": "merchant_demo", "scopes": ["customers:read"]},
    ):
        with pytest.raises(AccessDenied):
            registry.execute("get_transactions", context, {"reference": "r"})
    with pytest.raises(AccessDenied):
        registry.discover(MERCHANTS["merchant_demo"], intent=Intent.SETTLEMENT)
    assert calls == []


def test_scope_check_precedes_preconditions_and_handler():
    registry = ToolRegistry()
    calls = []
    register_read(
        registry,
        read_metadata(required_scopes=[Scope.CUSTOMERS_READ], preconditions=["ready"]),
        callback=lambda *a: calls.append("handler"),
        preconditions={"ready": lambda *a: calls.append("predicate")},
    )
    with pytest.raises(AccessDenied):
        registry.execute("get_transactions", demo_context("merchant_other"), {})
    assert calls == []


@pytest.mark.parametrize("result", [False, None, 1, "true"])
def test_only_true_preconditions_authorize_dispatch(result):
    registry = ToolRegistry()
    calls = []
    register_read(
        registry,
        read_metadata(preconditions=["evidence_available"]),
        callback=lambda *a: calls.append(True),
        preconditions={"evidence_available": lambda *a: result},
    )
    with pytest.raises(PreconditionFailed) as exc:
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})
    assert exc.value.precondition == "evidence_available"
    assert calls == []


def test_precondition_error_stops_dispatch_without_retry():
    registry = ToolRegistry()
    calls = []

    def unavailable(*args):
        calls.append("predicate")
        raise TimeoutError("source unavailable")

    register_read(
        registry,
        read_metadata(preconditions=["ready"]),
        callback=lambda *a: calls.append("handler"),
        preconditions={"ready": unavailable},
    )
    with pytest.raises(TimeoutError):
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})
    assert calls == ["predicate"]


def test_scoped_task_precondition_blocks_another_merchants_task():
    repo = MemoryTaskRepository()
    context = demo_context("merchant_demo")
    repo.save(
        context,
        Task(
            task_id="private-task",
            merchant_id=context.merchant_id,
            goal="Investigate",
            original_request="Original request",
            next_action="Read source evidence",
        ),
    )
    registry = ToolRegistry()
    seen = []
    register_read(
        registry,
        read_metadata(preconditions=["owns_task"]),
        callback=lambda ctx, inp: seen.append(ctx.actor_id) or handler(ctx, inp),
        preconditions={"owns_task": lambda ctx, inp: repo.get_task(ctx, inp.reference) is not None},
    )
    with pytest.raises(PreconditionFailed):
        registry.execute(
            "get_transactions", demo_context("merchant_other"), {"reference": "private-task"}
        )
    assert seen == []
    registry.execute("get_transactions", context, {"reference": "private-task"})
    assert seen == [context.actor_id]


def test_preparation_is_safe_to_dispatch_after_preconditions():
    registry = ToolRegistry()
    register_read(
        registry,
        read_metadata(name="draft_support_case", risk="preparation", preconditions=["ready"]),
        preconditions={"ready": lambda ctx, inp: inp.amount_paise > 0},
    )
    assert (
        registry.execute(
            "draft_support_case",
            demo_context("merchant_demo"),
            {"reference": "r", "amount_paise": 16680},
        ).amount_paise
        == 16680
    )


def test_predicates_cannot_change_inputs_passed_to_handler_or_later_predicates():
    class NestedInputs(Model):
        references: list[str]

    registry = ToolRegistry()

    def mutate(ctx, inp):
        inp.references.clear()
        return True

    registry.register(
        read_metadata(preconditions=["first", "second"]),
        NestedInputs,
        lambda ctx, inp: Result(merchant_id=ctx.merchant_id, reference=inp.references[0]),
        output_schema=Result,
        preconditions={"first": mutate, "second": lambda ctx, inp: inp.references == ["source"]},
    )
    inputs = {"references": ["source"]}
    assert (
        registry.execute("get_transactions", demo_context("merchant_demo"), inputs).reference
        == "source"
    )
    assert inputs == {"references": ["source"]}


def test_side_effects_remain_blocked_until_bm06_even_if_inputs_claim_approval():
    class ClaimedApproval(Inputs):
        approved: bool
        idempotency_key: str

    registry = ToolRegistry()
    calls = []
    register_read(registry, read_metadata(name="get_ticket_status"))
    registry.register(
        write_metadata(), ClaimedApproval, lambda *a: calls.append(True), output_schema=Result
    )
    tools = registry.discover(demo_context("merchant_demo"), intent=Intent.SETTLEMENT)
    assert tools[0].metadata.name == "create_support_ticket"
    assert tools[0].execution_gate == "approval_required"
    with pytest.raises(AccessDenied):
        registry.execute(
            "create_support_ticket",
            demo_context("merchant_demo"),
            {"reference": "r", "approved": True, "idempotency_key": "fake"},
        )
    assert calls == []


def test_write_discovery_and_execution_require_verifier_permissions_too():
    registry = ToolRegistry()
    register_write(registry)
    context = demo_context("merchant_demo").with_updates(scopes=frozenset({Scope.TICKETS_WRITE}))
    assert registry.discover(context, intent=Intent.SETTLEMENT) == []
    with pytest.raises(AccessDenied):
        registry.execute("create_support_ticket", context, {"reference": "r"})


@pytest.mark.parametrize(
    "changes",
    [
        {"intents": []},
        {"intents": [Intent.UNKNOWN]},
        {"required_scopes": []},
        {"required_scopes": ["invented:scope"]},
        {"name": "bad name"},
        {"description": " "},
        {"idempotency": "replay_anything"},
        {"preconditions": ["ready", "ready"]},
        {"approval_required": "true"},
        {"verification": {"tool_name": "status", "description": "check"}},
    ],
)
def test_invalid_metadata_is_rejected(changes):
    with pytest.raises(ValidationError):
        read_metadata(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"approval_required": False},
        {"idempotency": "none"},
        {"verification": None},
        {"verification": {"tool_name": "create_support_ticket", "description": "self check"}},
        {"required_scopes": [Scope.PAYMENTS_READ]},
    ],
)
def test_unsafe_write_policies_are_rejected(changes):
    with pytest.raises(ValidationError):
        write_metadata(**changes)


@pytest.mark.parametrize("predicates", [{}, {"wrong": lambda *a: True}, {"ready": None}])
def test_registration_rejects_unbound_or_invalid_preconditions(predicates):
    registry = ToolRegistry()
    with pytest.raises((ValueError, TypeError)):
        register_read(registry, read_metadata(preconditions=["ready"]), preconditions=predicates)
    assert registry.discover(demo_context("merchant_demo"), intent=Intent.SETTLEMENT) == []


def test_duplicate_registration_cannot_replace_handler(registry):
    with pytest.raises(ValueError, match="Duplicate"):
        register_read(registry, callback=lambda *a: None)
    assert (
        registry.execute(
            "get_transactions", demo_context("merchant_demo"), {"reference": "r"}
        ).reference
        == "r"
    )


@pytest.mark.parametrize("kind", ["missing", "preparation", "unsafe_retry", "irrelevant"])
def test_registration_requires_a_safe_relevant_verification_read(kind):
    registry = ToolRegistry()
    if kind != "missing":
        changes = {
            "preparation": {"risk": "preparation"},
            "unsafe_retry": {"idempotency": "none"},
            "irrelevant": {"intents": [Intent.WIN_BACK]},
        }[kind]
        register_read(registry, read_metadata(name="get_ticket_status", **changes))
    with pytest.raises(ValueError, match="verification read"):
        registry.register(write_metadata(), Inputs, handler, output_schema=Result)


def test_registration_revalidates_metadata_and_rejects_extra_accepting_schemas():
    registry = ToolRegistry()
    bad = read_metadata().model_copy(update={"risk": "side_effect"})
    with pytest.raises(ValidationError):
        register_read(registry, bad)

    class LooseModel(BaseModel):
        reference: str

    class ExtraModel(Inputs):
        model_config = ConfigDict(extra="allow")

    for schema in (LooseModel, ExtraModel, dict):
        with pytest.raises(TypeError):
            registry.register(read_metadata(), schema, handler, output_schema=Result)
        with pytest.raises(TypeError):
            registry.register(read_metadata(), Inputs, handler, output_schema=schema)


def test_registration_rejects_async_handlers_and_predicates():
    async def asynchronous(*args):
        return True

    registry = ToolRegistry()
    with pytest.raises(TypeError):
        register_read(registry, callback=asynchronous)
    with pytest.raises(TypeError):
        register_read(
            registry, read_metadata(preconditions=["ready"]), preconditions={"ready": asynchronous}
        )

    class AsyncAdapter:
        async def __call__(self, context, inputs):
            return handler(context, inputs)

    with pytest.raises(TypeError):
        register_read(registry, callback=AsyncAdapter())


def test_handler_cannot_return_another_merchants_record():
    registry = ToolRegistry()
    register_read(
        registry,
        callback=lambda ctx, inp: Result(merchant_id="merchant_other", reference=inp.reference),
    )
    with pytest.raises(AccessDenied):
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"reference": "r"},
        {"reference": "r", "merchant_id": "merchant_demo", "amount_paise": "123"},
        {"reference": "r", "merchant_id": "merchant_demo", "extra": True},
    ],
)
def test_invalid_handler_results_cannot_be_reported_as_success(result):
    registry = ToolRegistry()
    register_read(registry, callback=lambda *a: result)
    with pytest.raises(InvalidToolOutput):
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})


def test_tampered_output_model_is_revalidated():
    registry = ToolRegistry()
    invalid = Result(merchant_id="merchant_demo", reference="r").model_copy(
        update={"amount_paise": -1}
    )
    register_read(registry, callback=lambda *a: invalid)
    with pytest.raises(InvalidToolOutput):
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})


def test_strict_json_inputs_accept_iso_dates_and_enum_values():
    class DatedInputs(Model):
        day: date
        intent: Intent

    registry = ToolRegistry()
    registry.register(
        read_metadata(),
        DatedInputs,
        lambda ctx, inp: Result(merchant_id=ctx.merchant_id, reference=inp.day.isoformat()),
        output_schema=Result,
    )
    assert (
        registry.execute(
            "get_transactions",
            demo_context("merchant_demo"),
            {"day": "2026-11-14", "intent": "settlement"},
        ).reference
        == "2026-11-14"
    )


def test_read_errors_are_propagated_once_for_bm08_to_handle():
    calls = []

    def timed_out(*args):
        calls.append(True)
        raise TimeoutError("scripted report timeout")

    registry = ToolRegistry()
    register_read(registry, callback=timed_out)
    with pytest.raises(TimeoutError):
        registry.execute("get_transactions", demo_context("merchant_demo"), {"reference": "r"})
    assert calls == [True]
