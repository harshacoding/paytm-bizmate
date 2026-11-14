from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from bizmate.domain.models import Model

ConversationTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
ClientMessageId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
LanguageTag = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$", max_length=63
    ),
]
ChatContent = Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class Conversation(Model):
    conversation_id: str
    merchant_id: str
    title: ConversationTitle
    preferred_language: LanguageTag = "en"
    created_at: datetime
    updated_at: datetime


class ConversationMessage(Model):
    message_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    language: LanguageTag = "und"
    sequence: int = Field(gt=0)
    created_at: datetime


class ConversationTurn(Model):
    client_message_id: str
    user_message: ConversationMessage
    assistant_message: ConversationMessage


class CreateConversationRequest(Model):
    title: ConversationTitle = "New conversation"
    preferred_language: LanguageTag = "en"


class UpdateConversationLanguageRequest(Model):
    preferred_language: LanguageTag


class SendConversationMessageRequest(Model):
    content: ChatContent
    language: LanguageTag | None = None
    client_message_id: ClientMessageId | None = None

    @field_validator("content")
    @classmethod
    def require_nonblank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must contain non-whitespace text")
        return value
