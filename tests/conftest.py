import sqlite3

import pytest


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE messages (
            chat_jid TEXT,
            sender TEXT,
            content TEXT,
            timestamp TIMESTAMP
        )
        """
    )
    messages = [
        ("jid-1", "Alice", "Hello", "2024-01-01T10:00:00"),
        ("jid-3", "Eve", "Anyone here?", "2024-01-01T10:00:30"),
        ("jid-1", "Bob", "Hi there", "2024-01-01T10:01:00"),
        ("jid-1", "Alice", "How are you?", "2024-01-01T10:02:00"),
        ("jid-3", "Eve", "Guess not", "2024-01-01T10:02:30"),
        ("jid-2", "Charlie", "Hey", "2024-01-02T09:00:00"),
        ("jid-2", "Dave", "Yo", "2024-01-02T09:01:00"),
        ("jid-2", "Charlie", "What's up?", "2024-01-02T09:02:00"),
        ("jid-1", "Bob", "Good, you?", "2024-01-03T18:00:00"),
        ("jid-1", "Alice", "Doing great!", "2024-01-03T18:01:00"),
        ("jid-3", "Eve", "Finally someone", "2024-01-03T18:02:00"),
    ]
    conn.executemany(
        "INSERT INTO messages (chat_jid, sender, content, timestamp) VALUES (?, ?, ?, ?)",
        messages,
    )
    conn.commit()
    return conn
