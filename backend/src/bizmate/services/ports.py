"""BM-04: implement stateful mock adapters behind these boundaries; never live providers."""

from typing import Protocol

from bizmate.domain.context import MerchantContext
from bizmate.domain.models import Evidence, Receipt


class SettlementService(Protocol):
    def records(self, context: MerchantContext, task_id: str) -> list[Evidence]: ...
    def fresh_credits(
        self, context: MerchantContext, task_id: str, after_reference: str
    ) -> list[Evidence]: ...


class SupportService(Protocol):
    def create(
        self, context: MerchantContext, task_id: str, summary: str, idempotency_key: str
    ) -> Receipt: ...
    def status(self, context: MerchantContext, reference: str) -> str: ...


class CampaignService(Protocol):
    def send(
        self, context: MerchantContext, task_id: str, approved_input_hash: str, idempotency_key: str
    ) -> Receipt: ...
    def delivery(self, context: MerchantContext, reference: str) -> dict[str, int]: ...
