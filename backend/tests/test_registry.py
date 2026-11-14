import pytest
from pydantic import ValidationError

from bizmate.domain.errors import AccessDenied, FeaturePending
from bizmate.domain.models import Model, Scope
from bizmate.services.demo import MERCHANTS, demo_context
from bizmate.tools.registry import ToolMetadata, ToolRegistry


class Inputs(Model):
    reference: str


def test_read_dispatch_validates_inputs_and_injects_session():
    registry = ToolRegistry()
    registry.register(
        ToolMetadata(
            name="read",
            description="fixture",
            category="payment",
            risk="read",
            required_scopes=["payments:read"],
        ),
        Inputs,
        lambda merchant, inputs: (merchant.merchant_id, inputs.reference),
    )
    assert registry.execute("read", demo_context("merchant_demo"), {"reference": "r"}) == (
        "merchant_demo",
        "r",
    )
    with pytest.raises(ValidationError):
        registry.execute(
            "read", demo_context("merchant_demo"), {"reference": "r", "merchant_id": "x"}
        )
    with pytest.raises(KeyError):
        registry.execute("nonexistent", demo_context("merchant_demo"), {})


def test_write_handler_never_called_and_scopes_are_checked():
    registry = ToolRegistry()
    called = []
    registry.register(
        ToolMetadata(
            name="send",
            description="fixture",
            category="campaign",
            risk="side_effect",
            approval_required=True,
            required_scopes=["campaigns:write"],
        ),
        Inputs,
        lambda *args: called.append(True),
    )
    assert registry.discover(demo_context("merchant_other")) == []
    with pytest.raises(PermissionError):
        registry.execute("send", demo_context("merchant_other"), {"reference": "r"})
    with pytest.raises(FeaturePending):
        registry.execute("send", demo_context("merchant_demo"), {"reference": "r"})
    assert called == []


def test_read_permissions_apply_at_execution_and_handler_gets_context():
    registry = ToolRegistry()
    calls = []
    registry.register(
        ToolMetadata(
            name="customers",
            description="Read customers",
            category="crm",
            risk="read",
            required_scopes=[Scope.CUSTOMERS_READ],
        ),
        Inputs,
        lambda context, inputs: calls.append((context.actor_id, context.merchant_id)),
    )
    with pytest.raises(AccessDenied):
        registry.execute("customers", demo_context("merchant_other"), {"reference": "r"})
    with pytest.raises(AccessDenied):
        registry.execute("customers", MERCHANTS["merchant_demo"], {"reference": "r"})
    assert calls == []
    registry.execute("customers", demo_context("merchant_demo"), {"reference": "r"})
    assert calls == [("demo_actor_merchant_demo", "merchant_demo")]


def test_tool_schema_cannot_override_out_of_band_identity():
    class SpoofedInputs(Inputs):
        merchant_id: str

    registry = ToolRegistry()
    called = []
    registry.register(
        ToolMetadata(name="spoof", description="Bad adapter", category="test", risk="read"),
        SpoofedInputs,
        lambda *args: called.append(True),
    )
    with pytest.raises(AccessDenied):
        registry.execute(
            "spoof",
            demo_context("merchant_demo"),
            {"reference": "r", "merchant_id": "merchant_other"},
        )
    assert called == []
