from bizmate.domain.models import Intent, Scope
from bizmate.services.mocks import MockServices
from bizmate.tools.registry import ToolMetadata, ToolRegistry
from bizmate.workflows.settlement import (
    ReconciliationRequest,
    SettlementProof,
    prepare_settlement_proof,
)


def register_settlement_tools(registry: ToolRegistry, services: MockServices):
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
