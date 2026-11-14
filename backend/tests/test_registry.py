import pytest
from pydantic import ValidationError

from bizmate.domain.errors import FeaturePending
from bizmate.domain.models import Model
from bizmate.services.demo import MERCHANTS
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
    assert registry.execute("read", MERCHANTS["merchant_demo"], {"reference": "r"}) == (
        "merchant_demo",
        "r",
    )
    with pytest.raises(ValidationError):
        registry.execute("read", MERCHANTS["merchant_demo"], {"reference": "r", "merchant_id": "x"})
    with pytest.raises(KeyError):
        registry.execute("nonexistent", MERCHANTS["merchant_demo"], {})


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
    assert registry.discover(MERCHANTS["merchant_other"]) == []
    with pytest.raises(PermissionError):
        registry.execute("send", MERCHANTS["merchant_other"], {"reference": "r"})
    with pytest.raises(FeaturePending):
        registry.execute("send", MERCHANTS["merchant_demo"], {"reference": "r"})
    assert called == []
