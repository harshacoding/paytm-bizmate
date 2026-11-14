from bizmate.domain.models import Model, Scope
from bizmate.domain.types import Identifier, InputHash, MessageText, ShortText
from bizmate.services.mocks import MockServices
from bizmate.tools.registry import ToolMetadata, ToolRegistry


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


def register_mock_tools(registry: ToolRegistry, services: MockServices):
    for name, scopes, schema, handler in [
        (
            "get_transactions",
            [Scope.PAYMENTS_READ],
            NoInputs,
            lambda context, inputs: services.transactions(context),
        ),
        (
            "get_settlement_report",
            [Scope.PAYMENTS_READ, Scope.TASKS_READ],
            TaskInputs,
            lambda context, inputs: services.records(context, inputs.task_id),
        ),
        (
            "get_refunds_and_chargebacks",
            [Scope.PAYMENTS_READ],
            NoInputs,
            lambda context, inputs: services.deductions(context),
        ),
        (
            "get_customers_and_orders",
            [Scope.CUSTOMERS_READ],
            NoInputs,
            lambda context, inputs: services.customers(context),
        ),
        (
            "get_ticket_status",
            [Scope.TICKETS_WRITE],
            ReferenceInputs,
            lambda context, inputs: services.status(context, inputs.reference),
        ),
        (
            "get_campaign_delivery_status",
            [Scope.CAMPAIGNS_WRITE],
            ReferenceInputs,
            lambda context, inputs: services.delivery(context, inputs.reference),
        ),
    ]:
        registry.register(
            ToolMetadata(
                name=name,
                description=f"Read synthetic {name}",
                category="synthetic",
                risk="read",
                required_scopes=scopes,
            ),
            schema,
            handler,
        )
    registry.register(
        ToolMetadata(
            name="create_support_ticket",
            description="Create synthetic support ticket",
            category="support",
            risk="side_effect",
            required_scopes=[Scope.TASKS_READ, Scope.TICKETS_WRITE],
            approval_required=True,
            idempotency="merchant_action_key",
            verification_tool="get_ticket_status",
        ),
        TicketInputs,
        lambda context, inputs: services.create(
            context, inputs.task_id, inputs.summary, inputs.idempotency_key
        ),
    )
    registry.register(
        ToolMetadata(
            name="send_campaign",
            description="Simulate approved campaign delivery",
            category="campaign",
            risk="side_effect",
            required_scopes=[Scope.TASKS_READ, Scope.CAMPAIGNS_WRITE],
            approval_required=True,
            idempotency="merchant_action_key",
            verification_tool="get_campaign_delivery_status",
        ),
        SendInputs,
        lambda context, inputs: services.send(
            context, inputs.task_id, inputs.approved_input_hash, inputs.idempotency_key
        ),
    )
