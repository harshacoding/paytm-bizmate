from pydantic import Field

from bizmate.domain.models import Conversation, LanguageCode, Message, Model
from bizmate.domain.types import Identifier, MessageText, ShortText


class ConversationMessage(Message):
    sequence: int = Field(gt=0)
    # Legacy language is a declared hint. Actual detection and output use shared fields.
    language: str | None = Field(
        default=None, description="Declared legacy hint, separate from detection"
    )


class ConversationTurn(Model):
    client_message_id: Identifier
    user_message: ConversationMessage
    assistant_message: ConversationMessage


class CreateConversationRequest(Model):
    title: ShortText = "New conversation"
    preferred_language: LanguageCode | None = None


class UpdateConversationLanguageRequest(Model):
    preferred_language: LanguageCode


class SendConversationMessageRequest(Model):
    content: MessageText
    language: LanguageCode | None = None
    client_message_id: Identifier | None = None


__all__ = [
    "Conversation",
    "ConversationMessage",
    "ConversationTurn",
    "CreateConversationRequest",
    "SendConversationMessageRequest",
    "UpdateConversationLanguageRequest",
]
