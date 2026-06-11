from datetime import datetime

from pydantic import BaseModel

class Chat(BaseModel):
    jid: str
    name: str | None = None
    last_message_time: datetime | None = None
    last_message: str | None = None
    last_sender: str | None = None
    last_is_from_me: bool | None = None

    @property
    def is_group(self) -> bool:
        """Determine if chat is a group based on JID pattern."""
        return self.jid.endswith("@g.us")

class Message(BaseModel):
    id: str
    timestamp: datetime
    sender: str
    content: str
    is_from_me: bool
    chat_jid: str
    chat_name: str | None = None
    media_type: str | None = None
    quoted_message_id: str | None = None
    inserted_at: datetime | None = None

class Contact(BaseModel):
    jid: str
    name: str | None = None
    phone: str
    message_count: int | None = None

class MessageContext(BaseModel):
    message: Message
    before: list[Message]
    after: list[Message]