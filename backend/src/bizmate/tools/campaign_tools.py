from bizmate.domain.models import Intent, Scope
from bizmate.services.mocks import MockServices
from bizmate.tools.registry import ToolMetadata, ToolRegistry
from bizmate.workflows.campaign import CustomerSegment, SegmentRequest, prepare_customer_segment


def register_campaign_tools(registry: ToolRegistry, services: MockServices):
    registry.register(
        ToolMetadata(
            name="segment_inactive_customers",
            description=(
                "Find consenting inactive customers and calculate synthetic cost in integer paise"
            ),
            category="campaign",
            intents=[Intent.WIN_BACK],
            risk="preparation",
            required_scopes=[Scope.CUSTOMERS_READ],
        ),
        SegmentRequest,
        lambda context, inputs: prepare_customer_segment(context, services, inputs),
        output_schema=CustomerSegment,
    )
