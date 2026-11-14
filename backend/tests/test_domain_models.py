from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from bizmate.domain.models import (
    Approval,
    CampaignPreview,
    CapabilityGap,
    CreateTaskRequest,
    Evidence,
    Merchant,
    PlanStep,
    Receipt,
    Scope,
    Task,
    TaskStatus,
    ToolExecution,
    Verification,
)
from bizmate.domain.types import MAX_SAFE_INTEGER, Money, Paise

STAMP = datetime(2026, 11, 14, 4, tzinfo=UTC)
BASE = {"task_id": "task_a", "merchant_id": "merchant_demo"}


def make_task(**changes):
    return Task(
        **{
            **BASE,
            "goal": "Explain a settlement",
            "original_request": "Why is it short?",
            "next_action": "Investigate",
            "created_at": STAMP,
            "updated_at": STAMP,
            **changes,
        }
    )


def records():
    return {
        "plan": (PlanStep(**BASE, step_id="read", tool_name="get_transactions"),),
        "evidence": (
            Evidence(
                **BASE,
                evidence_id="e1",
                source="mock_bank",
                source_reference="fixture:credit-001",
                description="Bank credit",
                amount_paise=1840000,
            ),
        ),
        "approvals": (
            Approval(
                **BASE,
                approval_id="a1",
                action="create_ticket",
                approved_inputs={"summary": "short credit"},
                input_hash="a" * 64,
            ),
        ),
        "receipts": (
            Receipt(
                **BASE,
                receipt_id="r1",
                external_reference="ticket-1",
                action="create_ticket",
                idempotency_key="once-1",
                input_hash="a" * 64,
                created_at=STAMP,
            ),
        ),
        "tool_executions": (
            ToolExecution(
                **BASE,
                execution_id="x1",
                tool_name="get_transactions",
                input_hash="a" * 64,
                outcome="succeeded",
            ),
        ),
        "capability_gaps": (
            CapabilityGap(
                **BASE, gap_id="g1", requested_capability="bank_change", reason="No authorized tool"
            ),
        ),
    }


def verification(**changes):
    return Verification(
        **{
            **BASE,
            "verification_id": "v1",
            "receipt_id": "r1",
            "tool_name": "get_ticket_status",
            "verified": True,
            "evidence_reference": "ticket-read-1",
            "verified_at": STAMP,
            **changes,
        }
    )


@pytest.mark.parametrize("value", [True, False, 1.5, "16680", None, MAX_SAFE_INTEGER + 1])
def test_money_rejects_coercion_and_values_js_cannot_represent_exactly(value):
    with pytest.raises(ValidationError):
        TypeAdapter(Money).validate_python(value)


def test_money_has_exact_boundary_and_signed_evidence_support():
    for value in [0, 16680, MAX_SAFE_INTEGER]:
        assert TypeAdapter(Money).validate_json(str(value)) == value
    with pytest.raises(ValidationError):
        TypeAdapter(Money).validate_python(-1)
    assert TypeAdapter(Paise).validate_python(-16680) == -16680
    assert TypeAdapter(Paise).validate_python(-MAX_SAFE_INTEGER) == -MAX_SAFE_INTEGER
    with pytest.raises(ValidationError):
        TypeAdapter(Paise).validate_python(-MAX_SAFE_INTEGER - 1)
    evidence = records()["evidence"][0].with_updates(amount_paise=-80000)
    assert evidence.amount_paise == -80000


@pytest.mark.parametrize(
    "changes",
    [
        {"merchant_id": "../other"},
        {"task_id": "  "},
        {"goal": "  "},
        {"status": "done"},
        {"updated_at": STAMP - timedelta(seconds=1)},
        {"created_at": datetime(2026, 11, 14)},
        {"next_run_at": datetime(2026, 11, 15)},
        {"simulated": "false"},
        {"unexpected": "ignored?"},
    ],
)
def test_task_rejects_invalid_identity_state_time_and_unknown_fields(changes):
    with pytest.raises(ValidationError):
        make_task(**changes)


def test_models_are_frozen_and_validated_replacements_do_not_change_original():
    task = make_task()
    with pytest.raises(ValidationError):
        task.merchant_id = "merchant_other"
    with pytest.raises(ValidationError):
        task.with_updates(goal=" ")
    updated = task.with_updates(goal="A revised goal")
    assert updated.goal == "A revised goal" and task.goal == "Explain a settlement"
    assert isinstance(task.events, tuple)


@pytest.mark.parametrize("scope", ["admin", "*", "bank_account:write"])
def test_unknown_scopes_cannot_be_introduced(scope):
    with pytest.raises(ValidationError):
        Merchant(merchant_id="m", display_name="Store", scopes=[scope])


def test_scopes_are_immutable_and_messages_cannot_smuggle_authority():
    merchant = Merchant(merchant_id="m", display_name="Store", scopes=[Scope.TASKS_READ])
    assert merchant.scopes == frozenset({Scope.TASKS_READ})
    with pytest.raises(ValidationError):
        CreateTaskRequest(message="Hello", scopes=[Scope.TASKS_WRITE])
    assert CreateTaskRequest(message="  नमस्ते  ").message == "  नमस्ते  "


@pytest.mark.parametrize(
    "collection",
    ["plan", "evidence", "approvals", "receipts", "tool_executions", "capability_gaps"],
)
@pytest.mark.parametrize("changed", [{"merchant_id": "merchant_other"}, {"task_id": "task_other"}])
def test_attached_records_cannot_cross_task_or_merchant(collection, changed):
    record = records()[collection][0].with_updates(**changed)
    with pytest.raises(ValidationError, match="same task and merchant"):
        make_task(**{collection: [record]})


@pytest.mark.parametrize(
    "collection",
    ["plan", "evidence", "approvals", "receipts", "tool_executions", "capability_gaps"],
)
def test_duplicate_record_ids_rejected(collection):
    record = records()[collection][0]
    with pytest.raises(ValidationError, match="Duplicate"):
        make_task(**{collection: [record, record]})


def test_plan_is_a_valid_dependency_graph():
    first = records()["plan"][0]
    second = PlanStep(
        **BASE, step_id="reconcile", tool_name="reconcile_settlement", dependencies=["read"]
    )
    assert len(make_task(plan=[second, first]).plan) == 2  # Order need not be topological.
    with pytest.raises(ValidationError, match="cycle"):
        make_task(plan=[second])  # Missing read dependency.
    with pytest.raises(ValidationError, match="cycle"):
        make_task(plan=[first.with_updates(dependencies=["reconcile"]), second])
    for dependencies in [["read"], ["other", "other"]]:
        with pytest.raises(ValidationError):
            first.with_updates(dependencies=dependencies)


@pytest.mark.parametrize("decision", ["approved", "cancelled"])
def test_decided_approval_requires_actor_and_aware_timestamp(decision):
    approval = records()["approvals"][0]
    with pytest.raises(ValidationError):
        approval.with_updates(decision=decision)
    decided = approval.with_updates(decision=decision, approver="operator", decided_at=STAMP)
    assert decided.decision == decision
    with pytest.raises(ValidationError):
        decided.with_updates(decided_at=datetime(2026, 11, 14))


def test_pending_approval_cannot_claim_a_decision_or_invalid_hash():
    approval = records()["approvals"][0]
    for changes in [{"approver": "operator"}, {"decided_at": STAMP}, {"input_hash": "pretend"}]:
        with pytest.raises(ValidationError):
            approval.with_updates(**changes)


def test_verification_links_and_completion_are_validated():
    receipt = records()["receipts"][0]
    with pytest.raises(ValidationError, match="receipt not attached"):
        make_task(verifications=[verification()])
    with pytest.raises(ValidationError, match="same task and merchant"):
        make_task(receipts=[receipt], verifications=[verification(merchant_id="merchant_other")])
    with pytest.raises(ValidationError):
        verification(verified="true")
    for changes in [
        {},
        {"receipts": [receipt]},
        {"receipts": [receipt], "verifications": [verification(verified=False)]},
    ]:
        with pytest.raises(ValidationError, match="independent read"):
            make_task(status=TaskStatus.COMPLETED, **changes)
    complete = make_task(
        status=TaskStatus.COMPLETED, receipts=[receipt], verifications=[verification()]
    )
    assert Task.model_validate_json(complete.model_dump_json()) == complete
    for changes in [
        {"plan": records()["plan"]},
        {"approvals": records()["approvals"]},
        {"next_run_at": STAMP + timedelta(days=1)},
    ]:
        with pytest.raises(ValidationError):
            complete.with_updates(**changes)


def test_completion_uses_latest_verification_and_rejects_conflicting_reads():
    receipt = records()["receipts"][0]
    latest_failure = verification(
        verification_id="v2", verified=False, verified_at=STAMP + timedelta(seconds=1)
    )
    for reads in [
        [verification(), latest_failure],
        [verification(), verification(verification_id="v2", verified=False)],
    ]:
        with pytest.raises(ValidationError, match="independent read"):
            make_task(status=TaskStatus.COMPLETED, receipts=[receipt], verifications=reads)
    recovered = make_task(
        status=TaskStatus.COMPLETED,
        receipts=[receipt],
        verifications=[
            verification(verified=False),
            verification(verification_id="v2", verified_at=STAMP + timedelta(seconds=1)),
        ],
    )
    assert recovered.status == TaskStatus.COMPLETED
    for read in [
        verification(tool_name="create_ticket"),
        verification(verified_at=STAMP - timedelta(seconds=1)),
    ]:
        with pytest.raises(ValidationError):
            make_task(receipts=[receipt], verifications=[read])


def test_all_domain_records_survive_json_roundtrip():
    task = make_task(**records(), verifications=[verification()])
    assert Task.model_validate_json(task.model_dump_json()) == task


@pytest.mark.parametrize("value", [object(), {1, 2}, float("nan"), float("inf")])
def test_tool_and_approval_payloads_reject_non_json_and_nonfinite_values(value):
    with pytest.raises(ValidationError):
        records()["plan"][0].with_updates(inputs={"payload": value})
    with pytest.raises(ValidationError):
        records()["approvals"][0].with_updates(approved_inputs={"payload": value})


@pytest.mark.parametrize(
    "changes",
    [
        {"eligible_count": 201},
        {"delivered_count": 121},
        {"failed_count": -1},
        {"inactivity_days": 0},
        {"histories_count": True},
        {"estimated_cost_paise": 2.40},
    ],
)
def test_campaign_counts_and_cost_are_consistent(changes):
    values = {
        "histories_count": 200,
        "inactivity_days": 30,
        "eligible_count": 120,
        "estimated_cost_paise": 24000,
        "delivered_count": 118,
        "failed_count": 2,
    }
    with pytest.raises(ValidationError):
        CampaignPreview(**(values | changes))
