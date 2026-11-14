import json

from bizmate.domain.models import ActionResult, Evidence, Intent, Model, Scope, VerificationResult
from bizmate.domain.types import Count, Identifier, MessageText, ShortText
from bizmate.services.mock_models import CampaignPayload, CustomerHistory, PaymentRecord
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


class SendInputs(TaskInputs, CampaignPayload):
    pass


class PaymentRecords(Model):
    records: tuple[PaymentRecord, ...]


class EvidenceRecords(Model):
    evidence: tuple[Evidence, ...]


class TicketStatus(VerificationResult):
    status: ShortText


class CampaignDelivery(VerificationResult):
    delivered: Count
    failed: Count


def register_mock_tools(registry: ToolRegistry, services: MockServices):
    def ticket_status(context, inputs):
        status = services.status(context, inputs.reference)
        row = services.store.action(context.merchant_id, "create_support_ticket", inputs.reference)
        return TicketStatus(
            merchant_id=context.merchant_id,
            task_id=row["task_id"],
            external_reference=row["reference"],
            evidence_reference=row["reference"],
            verified=status in {"open", "closed"},
            status=status,
        )

    def campaign_delivery(context, inputs):
        counts = services.delivery(context, inputs.reference)
        row = services.store.action(context.merchant_id, "send_campaign", inputs.reference)
        return CampaignDelivery(
            merchant_id=context.merchant_id,
            task_id=row["task_id"],
            external_reference=row["reference"],
            evidence_reference=row["reference"],
            verified=sum(counts.values()) == len(json.loads(row["inputs"])["recipient_ids"]),
            **counts,
        )

    def create_ticket(context, inputs, *, idempotency_key):
        receipt = services.create(context, inputs.task_id, inputs.summary, idempotency_key)
        return ActionResult(external_reference=receipt.external_reference)

    def send_campaign(context, inputs, *, idempotency_key):
        payload = CampaignPayload.model_validate(inputs.model_dump(exclude={"task_id"}))
        digest = services.prepare_campaign(context, inputs.task_id, payload)
        receipt = services.send(context, inputs.task_id, digest, idempotency_key)
        return ActionResult(external_reference=receipt.external_reference)

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
            ticket_status,
        ),
        (
            "get_campaign_delivery_status",
            [Scope.CAMPAIGNS_WRITE],
            [Intent.WIN_BACK],
            ReferenceInputs,
            CampaignDelivery,
            campaign_delivery,
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
        create_ticket,
        output_schema=ActionResult,
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
        send_campaign,
        output_schema=ActionResult,
    )
