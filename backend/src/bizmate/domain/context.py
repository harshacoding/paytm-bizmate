from bizmate.domain.errors import AccessDenied
from bizmate.domain.models import Merchant, Model, Scope
from bizmate.domain.types import Identifier, ShortText


class MerchantContext(Model):
    """Server-resolved authority. Never deserialize this from request/model tool arguments."""

    actor_id: Identifier
    merchant_id: Identifier
    display_name: ShortText
    scopes: frozenset[Scope]

    def require(self, *scopes: Scope) -> None:
        if not set(scopes) <= self.scopes:
            raise AccessDenied("Session lacks a required scope")

    def require_owner(self, merchant_id: str) -> None:
        if merchant_id != self.merchant_id:
            raise AccessDenied("Record does not belong to the current merchant")

    def public_merchant(self) -> Merchant:
        return Merchant(
            merchant_id=self.merchant_id, display_name=self.display_name, scopes=self.scopes
        )


def require_context(context: MerchantContext) -> None:
    if not isinstance(context, MerchantContext):
        raise AccessDenied("A server-resolved merchant context is required")
