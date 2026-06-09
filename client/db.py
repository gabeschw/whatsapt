import os
import sqlite3

from client.models import Message


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.getenv("WHATSAPP_DB_PATH")
    conn = sqlite3.connect(path, check_same_thread=False)  # type: ignore
    conn.row_factory = sqlite3.Row
    return conn


def recent_messages(
    conn: sqlite3.Connection,
    n: int = 5,
    chat_jid: str | None = None,
) -> list[Message]:
    if chat_jid:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?",
            (chat_jid, n),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [Message(**row) for row in rows]
