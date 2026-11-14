from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Money = Annotated[int, Field(strict=True, ge=0)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


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


class Merchant(Model):
    merchant_id: str
    display_name: str
    scopes: list[str]


class TaskEvent(Model):
    event_id: str = Field(default_factory=new_id)
    kind: str
    message: str
    occurred_at: datetime = Field(default_factory=now)


class PlanStep(Model):
    step_id: str
    tool_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "done", "failed"] = "pending"


class Evidence(Model):
    evidence_id: str
    source: str
    source_reference: str
    description: str
    amount_paise: Money | None = None
    captured_at: datetime = Field(default_factory=now)


class Approval(Model):
    approval_id: str
    task_id: str
    merchant_id: str
    action: str
    approved_inputs: dict[str, Any]
    input_hash: str
    decision: Literal["pending", "approved", "cancelled"] = "pending"
    approver: str | None = None
    decided_at: datetime | None = None


class Receipt(Model):
    receipt_id: str
    task_id: str
    external_reference: str
    input_hash: str
    created_at: datetime = Field(default_factory=now)


class Verification(Model):
    verification_id: str
    receipt_id: str
    tool_name: str
    verified: bool
    evidence_reference: str
    verified_at: datetime = Field(default_factory=now)


class ToolExecution(Model):
    execution_id: str
    task_id: str
    tool_name: str
    input_hash: str
    outcome: str
    error: str | None = None
    occurred_at: datetime = Field(default_factory=now)


class CapabilityGap(Model):
    gap_id: str
    merchant_id: str
    requested_capability: str
    reason: str
    handoff_reference: str | None = None


class Task(Model):
    task_id: str = Field(default_factory=new_id)
    merchant_id: str
    goal: str
    original_request: str
    intent: Intent = Intent.UNKNOWN
    status: TaskStatus = TaskStatus.CREATED
    plan: list[PlanStep] = Field(default_factory=list)
    events: list[TaskEvent] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    receipts: list[Receipt] = Field(default_factory=list)
    verifications: list[Verification] = Field(default_factory=list)
    next_action: str
    next_run_at: datetime | None = None
    checkpoint_id: str | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    simulated: bool = True


class CreateTaskRequest(Model):
    message: Message


class ApprovalDecisionRequest(Model):
    decision: Literal["approve", "cancel"]
    input_hash: str = Field(min_length=1)


class ClarificationRequest(Model):
    message: Message


class ErrorResponse(Model):
    code: str
    message: str
    task_reference: str | None = None


class HealthResponse(Model):
    status: Literal["ok"] = "ok"
    mode: Literal["scaffold"] = "scaffold"
    storage: Literal["memory"] = "memory"
    workflows_implemented: bool = False


class SessionResponse(Model):
    merchant: Merchant
    mode: Literal["synthetic_local_demo"] = "synthetic_local_demo"


class SettlementPreview(Model):
    sales_paise: Money
    commission_paise: Money
    gst_paise: Money
    refunds_paise: Money
    chargeback_paise: Money
    expected_paise: Money
    credit_paise: Money
    residual_paise: Money
    source_references: list[str]


class CampaignPreview(Model):
    histories_count: int
    inactivity_days: int
    eligible_count: int
    estimated_cost_paise: Money
    delivered_count: int
    failed_count: int


class DemoPreview(Model):
    simulated: Literal[True] = True
    description: str
    settlement: SettlementPreview
    campaign: CampaignPreview
