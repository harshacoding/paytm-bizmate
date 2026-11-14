from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_domain_models import STAMP, make_task, records, verification

from bizmate.domain.lifecycle import transition_task
from bizmate.domain.models import TaskStatus as S


def test_planning_approval_execution_and_follow_up_path():
    task = make_task()
    path = [
        S.PLANNING,
        S.READY,
        S.RUNNING,
        S.AWAITING_APPROVAL,
        S.READY,
        S.RUNNING,
        S.VERIFYING,
        S.WAITING_EXTERNAL,
        S.RUNNING,
        S.VERIFYING,
    ]
    for index, target in enumerate(path, start=1):
        task = transition_task(
            task, target, "Next step", occurred_at=STAMP + timedelta(seconds=index)
        )
    assert task.status == S.VERIFYING
    assert len(task.events) == len(path)
    task = task.with_updates(receipts=records()["receipts"], verifications=[verification()])
    closed = transition_task(
        task, S.COMPLETED, "Verified complete", occurred_at=STAMP + timedelta(minutes=1)
    )
    assert closed.status == S.COMPLETED
    assert task.status == S.VERIFYING  # Original snapshot is unchanged.


def test_clarification_and_replanning_preserve_task_identity():
    task = make_task()
    for target in [S.PLANNING, S.AWAITING_INPUT, S.PLANNING, S.READY, S.RUNNING, S.PLANNING]:
        task = transition_task(task, target, "Clarify or replan")
    assert task.task_id == "task_a" and task.merchant_id == "merchant_demo"


@pytest.mark.parametrize(
    "source,target",
    [
        (S.CREATED, S.RUNNING),
        (S.CREATED, S.COMPLETED),
        (S.PLANNING, S.COMPLETED),
        (S.AWAITING_APPROVAL, S.RUNNING),
        (S.WAITING_EXTERNAL, S.COMPLETED),
        (S.ESCALATED, S.RUNNING),
        (S.FAILED, S.PLANNING),
        (S.READY, S.READY),
    ],
)
def test_invalid_and_skipped_transitions_rejected(source, target):
    with pytest.raises(ValueError, match="Invalid task transition"):
        transition_task(make_task(status=source), target, "Skip guards")


def test_completed_task_cannot_be_reopened_and_receipt_alone_cannot_complete():
    completed = make_task(
        status=S.COMPLETED, receipts=records()["receipts"], verifications=[verification()]
    )
    with pytest.raises(ValueError, match="Invalid task transition"):
        transition_task(completed, S.RUNNING, "Reopen")
    with pytest.raises(ValidationError, match="independent read"):
        transition_task(
            make_task(status=S.VERIFYING, receipts=records()["receipts"]),
            S.COMPLETED,
            "Only a receipt",
        )


def test_transition_time_cannot_lose_timezone_or_go_backwards():
    for timestamp in [STAMP.replace(tzinfo=None), STAMP - timedelta(seconds=1)]:
        with pytest.raises(ValueError):
            transition_task(make_task(), S.PLANNING, "Start", occurred_at=timestamp)
