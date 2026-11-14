# BM-05 typed tool registry

The registry and its policy tests are implemented. BM-04 mock adapters are registered at startup with typed outputs and relevant intents. BM-07 planner integration remains pending, and registry writes stay blocked until BM-06 supplies the approval engine. This change does not make settlement investigation, ticket creation or campaign sending work end to end.

## Registration contract for Devi

Use `bizmate.tools.registry.ToolRegistry` from backend bootstrap code. Registration is not exposed through HTTP or model tool calls. Bind only synthetic services and deterministic business functions from the PRD catalogue. There are no bank-account-change, refund execution, real payment or live marketing handlers.

Each definition requires:

- `ToolMetadata`: name, description, category, supported intents, risk and required scopes. Preconditions, approval, idempotency and verification policies are included explicitly where needed.
- An input schema and an output schema, both subclasses of the shared frozen, extra-forbid `Model`. JSON Schema for both is supplied to discovery callers.
- A synchronous handler accepting `(MerchantContext, validated_inputs)` and returning the output model or a matching dictionary. The registry stores the callable and exposes its qualified reference in planner metadata.
- A mapping of named synchronous predicates matching every declared precondition exactly. Predicates accept the same context and a detached input snapshot; only the boolean `True` passes. Keep predicates free of writes. Register task ownership, evidence availability and other resource/state checks here, using scoped repository/service reads.

Example read adapter (the service implementation and result fields belong to BM-04):

```python
from bizmate.domain.models import Evidence, Intent, Model, Scope
from bizmate.domain.types import Identifier
from bizmate.tools.registry import ToolMetadata, ToolRegistry

class ReadInputs(Model):
    task_id: Identifier

class ReadResult(Model):
    merchant_id: Identifier
    evidence: tuple[Evidence, ...]

def bind_settlement_read(registry: ToolRegistry, service, repository):
    def read(context, inputs):
        return ReadResult(
            merchant_id=context.merchant_id,
            evidence=tuple(service.records(context, inputs.task_id)),
        )

    registry.register(
        ToolMetadata(
            name="get_transactions",
            description="Read synthetic settlement evidence",
            category="settlement",
            intents=[Intent.SETTLEMENT],
            risk="read",
            required_scopes=[Scope.PAYMENTS_READ, Scope.TASKS_READ],
            preconditions=["owns_task"],
        ),
        ReadInputs,
        read,
        output_schema=ReadResult,
        preconditions={
            "owns_task": lambda context, inputs:
                repository.get_task(context, inputs.task_id) is not None,
        },
    )
```

Adapters must scope every underlying query and nested record to the supplied context. The registry rejects a mismatched top-level `merchant_id` in a typed result; it cannot infer ownership from arbitrary nested payloads. A task ID, customer ID or source reference is never proof of ownership.

## Discovery contract for Harsha

Call `registry.discover(context, intent=Intent.SETTLEMENT)` with the server-resolved context. Discovery returns detached, serializable `ToolDescriptor` instances in name order. It filters by intent and current permissions, including the permissions needed for an action's verification read. `Intent.UNKNOWN` returns no tools. The planner cannot request an unfiltered catalogue.

Descriptors contain metadata, input/output JSON Schemas, the handler reference and an execution gate. Discovery does not call predicates or authorize an action. Input-dependent preconditions are evaluated at dispatch. `approval_required` marks side effects that must use the BM-06 approval engine, even when the merchant has their scope.

## Dispatch and rejection behaviour

`registry.execute(name, context, inputs)` checks context, tool existence and current scopes before validating inputs or running predicates. Top-level `merchant_id`, `actor_id`, `scopes`, `merchant_context` and `session` arguments are rejected. Tool schemas must reject any other unknown fields. Nested document/customer text remains data; adapters must never use it as authority.

Inputs are validated as strict JSON: strings/floats/booleans cannot become integer money, while ISO dates and enum strings remain valid wire values. Original message whitespace and Unicode are preserved. Successful read/preparation handlers return revalidated, detached output models. Malformed output cannot become a successful tool result.

| Failure | Backend result |
| --- | --- |
| Unknown or unsupported tool | `UnknownTool` with `tool_name` |
| Untrusted context, missing scope, supplied identity or wrong result owner | `AccessDenied` |
| Invalid input shape/value | Pydantic `ValidationError`; non-JSON payloads raise `ValueError`/`TypeError` |
| Predicate returns anything except `True` | `PreconditionFailed` with tool and predicate names |
| Predicate or adapter raises an exception | Propagated once; handler is not retried |
| Malformed handler output | `InvalidToolOutput` with `tool_name` |
| Side-effect dispatch | `AccessDenied`; use the BM-06 approval engine instead |

The registry does not add transport routes, retries, audit persistence or workflow state changes. BM-07/BM-08 must translate failures into recorded task events and recovery. Catch policy failures separately from source timeouts and do not expose raw payloads or exception details to the merchant.

## Approval and verification boundary for BM-06

`read` means no external write; `preparation` means local drafting or deterministic calculation without an external write. Side effects must declare a write scope, `approval_required=True`, `idempotency="key_required"` and a `VerificationSpec` naming a separate read plus a plain description of what it verifies. Register that read first. It must be relevant to every intent of the write and declare `idempotency="safe_retry"`.

`safe_retry` describes safe repetition; `none` forbids assuming retry safety; `key_required` requires durable deduplication before a write. These are policies, not implementations of retry or deduplication. A registered verification read is not evidence that verification succeeded.

Direct registry side-effect dispatch remains blocked. The [BM-06 engine](BM_06_APPROVAL_ENGINE.md) supplies exact-input approvals, durable claims, receipts and independent verification. Write adapters return `ActionResult` and accept a server-supplied `idempotency_key`; verification adapters return `VerificationResult` from a separate stored-state read. Model-supplied approval flags or keys cannot unlock direct dispatch.

## Validation

`backend/tests/test_registry.py` covers relevant discovery, strict inputs, original content, permission rechecks, trusted context, merchant-scoped task preconditions, failed predicates, safe preparation, output validation, registration errors, verification permissions, unsupported tools and blocked side effects. BM-04 integration tests must additionally exercise real stateful mock services and cross-merchant nested records.
