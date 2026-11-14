from bizmate.domain.models import Evidence, Intent, Model, Receipt, Scope
from bizmate.domain.types import Count, Identifier, InputHash, MessageText, ShortText
from bizmate.services.mock_models import CustomerHistory, PaymentRecord
from bizmate.services.mocks import MockServices
from bizmate.tools.registry import ToolMetadata, ToolRegistry, VerificationSpec


class NoInputs(Model):
    pass


class TaskInputs(Model):
    task_id: Identifier


class ReferenceInputs(Model):
    reference: ShortText


class TicketInputs(TaskInputs):
    summary: MessageText
    idempotency_key: Identifier


class SendInputs(TaskInputs):
    approved_input_hash: InputHash
    idempotency_key: Identifier


class PaymentRecords(Model):
    records: tuple[PaymentRecord, ...]


class EvidenceRecords(Model):
    evidence: tuple[Evidence, ...]


class TicketStatus(Model):
    status: ShortText


class CampaignDelivery(Model):
    delivered: Count
    failed: Count


def register_mock_tools(registry: ToolRegistry, services: MockServices):
    for name, scopes, intents, schema, output, handler in [
        (
            "get_transactions",
            [Scope.PAYMENTS_READ],
            [Intent.SETTLEMENT],
            NoInputs,
            PaymentRecords,
            lambda context, inputs: PaymentRecords(records=services.transactions(context)),
        ),
        (
            "get_settlement_report",
            [Scope.PAYMENTS_READ, Scope.TASKS_READ],
            [Intent.SETTLEMENT],
            TaskInputs,
            EvidenceRecords,
            lambda context, inputs: EvidenceRecords(
                evidence=tuple(services.records(context, inputs.task_id))
            ),
        ),
        (
            "get_refunds_and_chargebacks",
            [Scope.PAYMENTS_READ],
            [Intent.SETTLEMENT],
            NoInputs,
            PaymentRecords,
            lambda context, inputs: PaymentRecords(records=services.deductions(context)),
        ),
        (
            "get_customers_and_orders",
            [Scope.CUSTOMERS_READ],
            [Intent.WIN_BACK],
            NoInputs,
            CustomerHistory,
            lambda context, inputs: services.customers(context),
        ),
        (
            "get_ticket_status",
            [Scope.TICKETS_WRITE],
            [Intent.SETTLEMENT, Intent.HANDOFF],
            ReferenceInputs,
            TicketStatus,
            lambda context, inputs: TicketStatus(status=services.status(context, inputs.reference)),
        ),
        (
            "get_campaign_delivery_status",
            [Scope.CAMPAIGNS_WRITE],
            [Intent.WIN_BACK],
            ReferenceInputs,
            CampaignDelivery,
            lambda context, inputs: CampaignDelivery(
                **services.delivery(context, inputs.reference)
            ),
        ),
    ]:
        registry.register(
            ToolMetadata(
                name=name,
                description=f"Read synthetic {name}",
                category="synthetic",
                risk="read",
                required_scopes=scopes,
                intents=intents,
            ),
            schema,
            handler,
            output_schema=output,
        )
    registry.register(
        ToolMetadata(
            name="create_support_ticket",
            description="Create synthetic support ticket",
            category="support",
            risk="side_effect",
            required_scopes=[Scope.TASKS_READ, Scope.TICKETS_WRITE],
            intents=[Intent.SETTLEMENT, Intent.HANDOFF],
            approval_required=True,
            idempotency="key_required",
            verification=VerificationSpec(
                tool_name="get_ticket_status", description="Read the independently stored ticket"
            ),
        ),
        TicketInputs,
        lambda context, inputs: services.create(
            context, inputs.task_id, inputs.summary, inputs.idempotency_key
        ),
        output_schema=Receipt,
    )
    registry.register(
        ToolMetadata(
            name="send_campaign",
            description="Simulate approved campaign delivery",
            category="campaign",
            risk="side_effect",
            required_scopes=[Scope.TASKS_READ, Scope.CAMPAIGNS_WRITE],
            intents=[Intent.WIN_BACK],
            approval_required=True,
            idempotency="key_required",
            verification=VerificationSpec(
                tool_name="get_campaign_delivery_status",
                description="Read independently stored campaign delivery counts",
            ),
        ),
        SendInputs,
        lambda context, inputs: services.send(
            context, inputs.task_id, inputs.approved_input_hash, inputs.idempotency_key
        ),
        output_schema=Receipt,
    )
