"""BM-04: implement stateful mock adapters behind these boundaries; never live providers."""

from typing import Protocol

from bizmate.domain.models import Evidence, Receipt
from bizmate.services.models import CampaignInputs, Credit, TicketInputs


class SettlementService(Protocol):
    def records(self, merchant_id: str) -> list[Evidence]: ...
    def fresh_credits(self, merchant_id: str, after_reference: str) -> list[Credit]: ...


class SupportService(Protocol):
    def create(self, merchant_id: str, inputs: TicketInputs, idempotency_key: str) -> Receipt: ...
    def status(self, merchant_id: str, reference: str) -> str: ...


class CampaignService(Protocol):
    def send(self, merchant_id: str, inputs: CampaignInputs, idempotency_key: str) -> Receipt: ...
    def delivery(self, merchant_id: str, reference: str) -> dict[str, int]: ...
