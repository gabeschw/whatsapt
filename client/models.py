from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel):
    timestamp: datetime
    sender: str
    content: str
    chat_jid: str | None = None