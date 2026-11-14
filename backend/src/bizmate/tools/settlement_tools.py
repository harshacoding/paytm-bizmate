from bizmate.domain.models import Intent, Model, Scope
from bizmate.domain.types import Identifier
from bizmate.services.mock_models import PaymentRecord
from bizmate.services.mocks import MockServices
from bizmate.tools.registry import ToolMetadata, ToolRegistry
from bizmate.workflows.settlement import (
    ReconciliationRequest,
    SettlementProof,
    prepare_settlement_proof,
)


class CreditInputs(Model):
    task_id: Identifier


class FollowUpRecords(Model):
    records: tuple[PaymentRecord, ...]


def register_settlement_tools(registry: ToolRegistry, services: MockServices):
    registry.register(
        ToolMetadata(
            name="get_settlement_follow_up",
            description="Read scoped settlement sources for fresh-credit validation",
            category="settlement",
            intents=[Intent.SETTLEMENT],
            risk="read",
            required_scopes=[Scope.PAYMENTS_READ, Scope.TASKS_READ],
        ),
        CreditInputs,
        lambda context, inputs: FollowUpRecords(
            records=services.follow_up_records(context, inputs.task_id)
        ),
        output_schema=FollowUpRecords,
    )
    registry.register(
        ToolMetadata(
            name="reconcile_settlement",
            description="Calculate a source-linked settlement proof using integer paise",
            category="settlement",
            intents=[Intent.SETTLEMENT],
            risk="preparation",
            required_scopes=[Scope.PAYMENTS_READ],
        ),
        ReconciliationRequest,
        lambda context, inputs: prepare_settlement_proof(context, services, inputs),
        output_schema=SettlementProof,
    )
