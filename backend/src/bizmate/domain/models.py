from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    model_validator,
)

from bizmate.domain.types import (
    Count,
    Identifier,
    InputHash,
    MessageText,
    Money,
    Paise,
    ShortText,
    Text,
)


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        allow_inf_nan=False,
        json_schema_serialization_defaults_required=True,
    )

    def with_updates(self, **changes: Any) -> Self:
        """Validated replacement. Pydantic's model_copy(update=...) skips validation."""
        return type(self).model_validate({**self.model_dump(), **changes})


class Scope(StrEnum):
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    TASKS_APPROVE = "tasks:approve"
    PAYMENTS_READ = "payments:read"
    CUSTOMERS_READ = "customers:read"
    TICKETS_WRITE = "tickets:write"
    CAMPAIGNS_WRITE = "campaigns:write"


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    AWAITING_INPUT = "AWAITING_INPUT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class Intent(StrEnum):
    SETTLEMENT = "settlement"
    WIN_BACK = "win_back"
    HANDOFF = "handoff"
    UNKNOWN = "unknown"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class LanguageCode(StrEnum):
    ENGLISH = "en"
    TELUGU = "te"
    HINDI = "hi"


class LanguageContext(Model):
    preferred_language: LanguageCode = LanguageCode.ENGLISH
    detected_language: LanguageCode | None = None
    response_language: LanguageCode | None = None


class Merchant(Model):
    merchant_id: Identifier
    display_name: ShortText
    preferred_language: LanguageCode = LanguageCode.ENGLISH
    scopes: frozenset[Scope]


class TaskEntity(Model):
    task_id: Identifier
    merchant_id: Identifier


class TaskEvent(Model):
    event_id: Identifier = Field(default_factory=new_id)
    kind: Identifier
    message: MessageText
    occurred_at: AwareDatetime = Field(default_factory=now)


class PlanStep(TaskEntity):
    step_id: Identifier
    tool_name: Identifier
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    dependencies: tuple[Identifier, ...] = ()
    status: Literal["pending", "running", "done", "failed"] = "pending"

    @model_validator(mode="after")
    def valid_dependencies(self) -> Self:
        if self.step_id in self.dependencies or len(set(self.dependencies)) != len(
            self.dependencies
        ):
            raise ValueError("Step dependencies must be unique and cannot include itself")
        return self


class Evidence(TaskEntity):
    evidence_id: Identifier
    source: ShortText
    source_reference: ShortText
    description: Text
    amount_paise: Paise | None = None
    captured_at: AwareDatetime = Field(default_factory=now)


class Approval(TaskEntity):
    approval_id: Identifier
    action: Identifier
    approved_inputs: dict[str, JsonValue]
    input_hash: InputHash
    decision: Literal["pending", "approved", "cancelled"] = "pending"
    approver: Identifier | None = None
    decided_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_decision(self) -> Self:
        if self.decision == "pending":
            if self.approver is not None or self.decided_at is not None:
                raise ValueError("Pending approval cannot contain a decision actor or time")
        elif self.approver is None or self.decided_at is None:
            raise ValueError("A decided approval requires its actor and time")
        return self


class Receipt(TaskEntity):
    receipt_id: Identifier
    external_reference: ShortText
    action: Identifier
    idempotency_key: Identifier
    input_hash: InputHash
    created_at: AwareDatetime = Field(default_factory=now)


class Verification(TaskEntity):
    verification_id: Identifier
    receipt_id: Identifier
    tool_name: Identifier
    verified: StrictBool
    evidence_reference: ShortText
    verified_at: AwareDatetime = Field(default_factory=now)


class ActionResult(Model):
    external_reference: ShortText


class VerificationResult(TaskEntity):
    external_reference: ShortText
    verified: StrictBool
    evidence_reference: ShortText


class ToolExecution(TaskEntity):
    execution_id: Identifier
    tool_name: Identifier
    input_hash: InputHash
    outcome: Literal["succeeded", "failed", "uncertain"]
    error: Text | None = None
    occurred_at: AwareDatetime = Field(default_factory=now)


class CapabilityGap(TaskEntity):
    gap_id: Identifier
    requested_capability: ShortText
    reason: Text
    handoff_reference: ShortText | None = None


class Task(TaskEntity):
    task_id: Identifier = Field(default_factory=new_id)
    revision: int = Field(default=0, strict=True, ge=0)
    conversation_id: Identifier | None = None
    goal: ShortText
    original_request: MessageText
    intent: Intent = Intent.UNKNOWN
    status: TaskStatus = TaskStatus.CREATED
    plan: tuple[PlanStep, ...] = ()
    events: tuple[TaskEvent, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    approvals: tuple[Approval, ...] = ()
    receipts: tuple[Receipt, ...] = ()
    verifications: tuple[Verification, ...] = ()
    tool_executions: tuple[ToolExecution, ...] = ()
    capability_gaps: tuple[CapabilityGap, ...] = ()
    workflow_data: dict[str, JsonValue] = Field(default_factory=dict)
    next_action: Text
    next_run_at: AwareDatetime | None = None
    checkpoint_id: Identifier | None = None
    created_at: AwareDatetime = Field(default_factory=now)
    updated_at: AwareDatetime = Field(default_factory=now)
    simulated: StrictBool = True

    @property
    def has_unresolved_execution(self) -> bool:
        return any(
            e.outcome == "uncertain"
            and not any(
                r.idempotency_key == e.execution_id
                and r.input_hash == e.input_hash
                and r.action == e.tool_name
                for r in self.receipts
            )
            for e in self.tool_executions
        )

    @model_validator(mode="after")
    def valid_task(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("Task updated_at cannot precede created_at")
        if self.next_run_at is not None and self.next_run_at < self.created_at:
            raise ValueError("Task next_run_at cannot precede created_at")
        collections = {
            "step_id": self.plan,
            "evidence_id": self.evidence,
            "approval_id": self.approvals,
            "receipt_id": self.receipts,
            "verification_id": self.verifications,
            "execution_id": self.tool_executions,
            "gap_id": self.capability_gaps,
        }
        for id_field, items in collections.items():
            if len({getattr(item, id_field) for item in items}) != len(items):
                raise ValueError(f"Duplicate {id_field} in task")
            if any(
                item.task_id != self.task_id or item.merchant_id != self.merchant_id
                for item in items
            ):
                raise ValueError("Attached records must belong to the same task and merchant")
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("Duplicate event_id in task")
        steps = {step.step_id: step for step in self.plan}
        remaining = set(steps)
        done: set[str] = set()
        while remaining:
            ready = {key for key in remaining if set(steps[key].dependencies) <= done}
            if not ready:
                raise ValueError("Plan contains missing dependencies or a cycle")
            done.update(ready)
            remaining -= ready
        receipts_by_id = {receipt.receipt_id: receipt for receipt in self.receipts}
        receipts = set(receipts_by_id)
        if any(v.receipt_id not in receipts for v in self.verifications):
            raise ValueError("Verification references a receipt not attached to this task")
        if any(v.verified_at < receipts_by_id[v.receipt_id].created_at for v in self.verifications):
            raise ValueError("Verification cannot precede its receipt")
        if any(v.tool_name == receipts_by_id[v.receipt_id].action for v in self.verifications):
            raise ValueError("Verification must use a separate read tool")
        if self.status == TaskStatus.COMPLETED:
            if self.has_unresolved_execution:
                raise ValueError("Completion cannot leave an uncertain execution unresolved")
            reads = {
                key: [v for v in self.verifications if v.receipt_id == key] for key in receipts
            }
            verified = set()
            for key, results in reads.items():
                if results:
                    latest = max(v.verified_at for v in results)
                    if all(v.verified for v in results if v.verified_at == latest):
                        verified.add(key)
            if not receipts or not receipts <= verified:
                raise ValueError(
                    "Completion requires a successful independent read for each receipt"
                )
            if any(step.status != "done" for step in self.plan):
                raise ValueError("Completion cannot leave unfinished plan steps")
            if any(approval.decision == "pending" for approval in self.approvals):
                raise ValueError("Completion cannot leave a pending approval")
            if self.next_run_at is not None:
                raise ValueError("A completed task cannot have a scheduled next run")
        return self


class Conversation(Model):
    conversation_id: Identifier = Field(default_factory=new_id)
    merchant_id: Identifier
    title: ShortText
    preferred_language: LanguageCode = LanguageCode.ENGLISH
    created_at: AwareDatetime = Field(default_factory=now)
    updated_at: AwareDatetime = Field(default_factory=now)

    @model_validator(mode="after")
    def valid_timestamps(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("Conversation updated_at cannot precede created_at")
        return self


class Message(Model):
    message_id: Identifier = Field(default_factory=new_id)
    conversation_id: Identifier
    merchant_id: Identifier
    role: MessageRole
    content: MessageText
    detected_language: LanguageCode | None = None
    response_language: LanguageCode | None = None
    task_id: Identifier | None = None
    created_at: AwareDatetime = Field(default_factory=now)


class ConversationThread(Model):
    """Complete conversation snapshot, including all tasks needed to resolve message links."""

    conversation: Conversation
    messages: tuple[Message, ...] = ()
    tasks: tuple[Task, ...] = ()

    @model_validator(mode="after")
    def valid_relationships(self) -> Self:
        for records in [self.messages, self.tasks]:
            if any(
                record.merchant_id != self.conversation.merchant_id
                or record.conversation_id != self.conversation.conversation_id
                for record in records
            ):
                raise ValueError("Conversation records must share its merchant and conversation ID")
        if len({message.message_id for message in self.messages}) != len(self.messages):
            raise ValueError("Duplicate message_id in conversation")
        task_ids = {task.task_id for task in self.tasks}
        if len(task_ids) != len(self.tasks):
            raise ValueError("Duplicate task_id in conversation")
        if any(
            message.task_id is not None and message.task_id not in task_ids
            for message in self.messages
        ):
            raise ValueError("Message references a task not attached to this conversation")
        return self


class CreateTaskRequest(Model):
    message: MessageText
    conversation_id: Identifier | None = None


class ApprovalDecisionRequest(Model):
    decision: Literal["approve", "cancel"]
    input_hash: InputHash


class ApprovalRequest(Model):
    action: Identifier
    inputs: dict[str, JsonValue]


class ExecuteActionRequest(Model):
    inputs: dict[str, JsonValue]


class ClarificationRequest(Model):
    message: MessageText


class ErrorResponse(Model):
    code: str
    message: str
    task_reference: str | None = None


class HealthResponse(Model):
    status: Literal["ok"] = "ok"
    mode: Literal["scaffold"] = "scaffold"
    storage: Literal["memory", "sqlite"] = "memory"
    workflows_implemented: bool = False


class SessionResponse(Model):
    merchant: Merchant
    actor_id: Identifier
    mode: Literal["synthetic_local_demo"] = "synthetic_local_demo"


class SettlementPreview(Model):
    sales_paise: Money
    commission_paise: Money
    gst_paise: Money
    refunds_paise: Money
    chargeback_paise: Money
    expected_paise: Paise
    credit_paise: Money
    residual_paise: Paise
    source_references: tuple[ShortText, ...] = Field(min_length=1)


class CampaignPreview(Model):
    histories_count: Count
    inactivity_days: Count = Field(gt=0)
    eligible_count: Count
    estimated_cost_paise: Money
    delivered_count: Count
    failed_count: Count

    @model_validator(mode="after")
    def valid_counts(self) -> Self:
        if self.eligible_count > self.histories_count:
            raise ValueError("Eligible audience exceeds histories analysed")
        if self.delivered_count + self.failed_count > self.eligible_count:
            raise ValueError("Delivery counts exceed the approved eligible audience")
        return self


class DemoPreview(Model):
    simulated: Literal[True] = True
    description: str
    settlement: SettlementPreview
    campaign: CampaignPreview
