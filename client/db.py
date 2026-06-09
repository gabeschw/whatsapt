import os
import sqlite3

from datetime import datetime

def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.getenv("WHATSAPP_DB_PATH", "./messages.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def recent_messages(
    conn: sqlite3.Connection,
    n: int = 5,
    chat_jid: str | None = None,
) -> list[sqlite3.Row]:
    if chat_jid:
        return conn.execute(
            "SELECT * FROM messages WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?",
            (chat_jid, n),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?",
        (n,),
    ).fetchall()


def print_messages(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("No messages found.")
        return
    for row in reversed(rows):
        ts = datetime.fromisoformat(row["timestamp"]).strftime("%Y-%m-%d %H:%M")
        sender = row["sender"] 
        content = row["content"]
        print(f"[{ts}] {sender}:\n{content}\n")
