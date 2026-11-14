import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from bizmate.domain.chat import Conversation, ConversationMessage, ConversationTurn
from bizmate.domain.models import new_id, now


class ConversationConflictError(Exception):
    """A client message ID has already been used with different user content."""


class ConversationRepository(Protocol):
    def create(
        self, merchant_id: str, title: str, preferred_language: str = "en"
    ) -> Conversation: ...
    def list_conversations(self, merchant_id: str) -> list[Conversation]: ...
    def get(self, merchant_id: str, conversation_id: str) -> Conversation | None: ...
    def set_preferred_language(
        self, merchant_id: str, conversation_id: str, language: str
    ) -> Conversation: ...
    def messages(
        self, merchant_id: str, conversation_id: str
    ) -> list[ConversationMessage] | None: ...
    def get_turn(
        self, merchant_id: str, conversation_id: str, client_message_id: str
    ) -> ConversationTurn | None: ...
    def save_turn(
        self,
        merchant_id: str,
        conversation_id: str,
        content: str,
        assistant_content: str,
        client_message_id: str,
        user_language: str | None = None,
        assistant_language: str = "en",
    ) -> ConversationTurn: ...


class SQLiteConversationRepository:
    """Chat records have their own lifecycle and no foreign keys to business tasks."""

    def __init__(self, database_path: str | Path):
        if str(database_path) == ":memory:":
            raise ValueError("SQLiteConversationRepository requires a filesystem database path")
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    merchant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (conversation_id, merchant_id)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS conversations_merchant_created
                   ON conversations (merchant_id, created_at, conversation_id)"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    merchant_id TEXT NOT NULL,
                    client_message_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
                    language TEXT NOT NULL DEFAULT 'und',
                    sequence INTEGER NOT NULL CHECK (sequence > 0),
                    created_at TEXT NOT NULL,
                    UNIQUE (conversation_id, sequence),
                    UNIQUE (conversation_id, client_message_id, role),
                    FOREIGN KEY (conversation_id, merchant_id)
                        REFERENCES conversations (conversation_id, merchant_id) ON DELETE CASCADE
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS messages_merchant_conversation
                   ON messages (merchant_id, conversation_id, sequence)"""
            )
            # Add language fields to databases created by the first BM-03 chat implementation.
            conversation_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(conversations)")
            }
            if "preferred_language" not in conversation_columns:
                connection.execute(
                    """ALTER TABLE conversations
                       ADD COLUMN preferred_language TEXT NOT NULL DEFAULT 'en'"""
                )
            message_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(messages)")
            }
            if "language" not in message_columns:
                connection.execute(
                    "ALTER TABLE messages ADD COLUMN language TEXT NOT NULL DEFAULT 'und'"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation.model_validate(dict(row))

    @staticmethod
    def _message(row: sqlite3.Row) -> ConversationMessage:
        return ConversationMessage.model_validate(
            {field: row[field] for field in ConversationMessage.model_fields}
        )

    def create(self, merchant_id: str, title: str, preferred_language: str = "en") -> Conversation:
        timestamp = now()
        conversation = Conversation(
            conversation_id=new_id(),
            merchant_id=merchant_id,
            title=title,
            preferred_language=preferred_language,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO conversations
                   (conversation_id, merchant_id, title, created_at, updated_at, preferred_language)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    conversation.conversation_id,
                    merchant_id,
                    conversation.title,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    conversation.preferred_language,
                ),
            )
        return conversation

    def list_conversations(self, merchant_id: str) -> list[Conversation]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT * FROM conversations WHERE merchant_id = ?
                   ORDER BY created_at, conversation_id""",
                (merchant_id,),
            ).fetchall()
        return [self._conversation(row) for row in rows]

    def get(self, merchant_id: str, conversation_id: str) -> Conversation | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE merchant_id = ? AND conversation_id = ?",
                (merchant_id, conversation_id),
            ).fetchone()
        return self._conversation(row) if row else None

    def set_preferred_language(
        self, merchant_id: str, conversation_id: str, language: str
    ) -> Conversation:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM conversations WHERE merchant_id = ? AND conversation_id = ?",
                (merchant_id, conversation_id),
            ).fetchone()
            if row is None:
                raise KeyError("Conversation not found")
            conversation = Conversation.model_validate(
                {**dict(row), "preferred_language": language}
            )
            conversation.updated_at = now()
            connection.execute(
                """UPDATE conversations SET preferred_language = ?, updated_at = ?
                   WHERE merchant_id = ? AND conversation_id = ?""",
                (
                    conversation.preferred_language,
                    conversation.updated_at.isoformat(),
                    merchant_id,
                    conversation_id,
                ),
            )
        return conversation

    def messages(self, merchant_id: str, conversation_id: str) -> list[ConversationMessage] | None:
        with closing(self._connect()) as connection:
            # Both checks share a read transaction, including when another worker deletes chat data.
            connection.execute("BEGIN")
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE merchant_id = ? AND conversation_id = ?",
                (merchant_id, conversation_id),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                """SELECT * FROM messages WHERE merchant_id = ? AND conversation_id = ?
                   ORDER BY sequence""",
                (merchant_id, conversation_id),
            ).fetchall()
        return [self._message(row) for row in rows]

    def _turn(
        self,
        connection: sqlite3.Connection,
        merchant_id: str,
        conversation_id: str,
        client_message_id: str,
    ) -> ConversationTurn | None:
        rows = connection.execute(
            """SELECT * FROM messages WHERE merchant_id = ? AND conversation_id = ?
               AND client_message_id = ? ORDER BY sequence""",
            (merchant_id, conversation_id, client_message_id),
        ).fetchall()
        if not rows:
            return None
        return ConversationTurn(
            client_message_id=client_message_id,
            user_message=self._message(rows[0]),
            assistant_message=self._message(rows[1]),
        )

    def get_turn(
        self, merchant_id: str, conversation_id: str, client_message_id: str
    ) -> ConversationTurn | None:
        with closing(self._connect()) as connection:
            return self._turn(connection, merchant_id, conversation_id, client_message_id)

    def save_turn(
        self,
        merchant_id: str,
        conversation_id: str,
        content: str,
        assistant_content: str,
        client_message_id: str,
        user_language: str | None = None,
        assistant_language: str = "en",
    ) -> ConversationTurn:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                """SELECT preferred_language FROM conversations
                   WHERE merchant_id = ? AND conversation_id = ?""",
                (merchant_id, conversation_id),
            ).fetchone()
            if exists is None:
                raise KeyError("Conversation not found")
            previous = self._turn(connection, merchant_id, conversation_id, client_message_id)
            if previous is not None:
                if previous.user_message.content != content or (
                    user_language is not None and previous.user_message.language != user_language
                ):
                    raise ConversationConflictError(
                        "Client message ID was used with different content"
                    )
                return previous
            last_sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
            timestamp = now().isoformat()
            for offset, (role, text, language) in enumerate(
                [
                    ("user", content, user_language or exists["preferred_language"]),
                    ("assistant", assistant_content, assistant_language),
                ],
                1,
            ):
                message = ConversationMessage(
                    message_id=new_id(),
                    conversation_id=conversation_id,
                    role=role,
                    content=text,
                    language=language,
                    sequence=last_sequence + offset,
                    created_at=timestamp,
                )
                connection.execute(
                    """INSERT INTO messages (message_id, conversation_id, merchant_id,
                       client_message_id, role, content, sequence, created_at, language)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        message.message_id,
                        conversation_id,
                        merchant_id,
                        client_message_id,
                        role,
                        text,
                        last_sequence + offset,
                        timestamp,
                        message.language,
                    ),
                )
            connection.execute(
                """UPDATE conversations SET updated_at = ?
                   WHERE merchant_id = ? AND conversation_id = ?""",
                (timestamp, merchant_id, conversation_id),
            )
            return self._turn(connection, merchant_id, conversation_id, client_message_id)
