from bizmate.domain.models import CapabilityGap, Merchant, new_id
from bizmate.tools.registry import ToolRegistry


def prepare_handoff(
    merchant: Merchant, requested_capability: str, registry: ToolRegistry
) -> CapabilityGap:
    available = {tool.name for tool in registry.discover(merchant)}
    if requested_capability in available:
        raise ValueError("This capability is available. Start its supported workflow.")
    return CapabilityGap(
        gap_id=new_id(),
        merchant_id=merchant.merchant_id,
        requested_capability=requested_capability,
        reason=(
            "This session has no permitted tool for the requested action. "
            "Human support must continue."
        ),
    )
