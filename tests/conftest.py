import sqlite3

import pytest


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            chat_jid TEXT,
            sender TEXT,
            content TEXT,
            timestamp TIMESTAMP,
            is_from_me BOOLEAN,
            media_type TEXT,
            filename TEXT,
            url TEXT,
            media_key BLOB,
            file_sha256 BLOB,
            file_enc_sha256 BLOB,
            file_length INTEGER,
            deleted_at TIMESTAMP,
            inserted_at TIMESTAMP,
            quoted_message_id TEXT
        );

        CREATE TABLE chats (
            jid TEXT PRIMARY KEY,
            name TEXT,
            last_message_time TIMESTAMP,
            ephemeral_expiration INTEGER DEFAULT 0,
            ephemeral_setting_timestamp INTEGER DEFAULT 0
        );
    """)

    messages = [
        ("msg-1",  "jid-1", "Alice",   "Hello",          "2024-01-01T10:00:00", 0),
        ("msg-2",  "jid-3", "Eve",     "Anyone here?",   "2024-01-01T10:00:30", 0),
        ("msg-3",  "jid-1", "Bob",     "Hi there",       "2024-01-01T10:01:00", 0),
        ("msg-4",  "jid-1", "Alice",   "How are you?",   "2024-01-01T10:02:00", 0),
        ("msg-5",  "jid-3", "Eve",     "Guess not",      "2024-01-01T10:02:30", 0),
        ("msg-6",  "jid-2", "Charlie", "Hey",            "2024-01-02T09:00:00", 0),
        ("msg-7",  "jid-2", "Dave",    "Yo",             "2024-01-02T09:01:00", 0),
        ("msg-8",  "jid-2", "Charlie", "What's up?",     "2024-01-02T09:02:00", 0),
        ("msg-9",  "jid-1", "Bob",     "Good, you?",     "2024-01-03T18:00:00", 0),
        ("msg-10", "jid-1", "Alice",   "Doing great!",   "2024-01-03T18:01:00", 0),
        ("msg-11", "jid-3", "Eve",     "Finally someone","2024-01-03T18:02:00", 0),
    ]
    conn.executemany(
        "INSERT INTO messages (id, chat_jid, sender, content, timestamp, is_from_me) VALUES (?, ?, ?, ?, ?, ?)",
        messages,
    )

    chats = [
        ("jid-1", "Group Chat 1", "2024-01-03T18:01:00"),
        ("jid-2", "Group Chat 2", "2024-01-02T09:02:00"),
        ("jid-3", "Group Chat 3", "2024-01-03T18:02:00"),
    ]
    conn.executemany(
        "INSERT INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)",
        chats,
    )
    conn.commit()
    return conn


@pytest.fixture
def whatsmeow_db_path(tmp_path):
    db_path = str(tmp_path / "whatsapp.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE whatsmeow_lid_map (pn TEXT, lid TEXT);
        CREATE TABLE whatsmeow_contacts (
            their_jid TEXT, full_name TEXT, push_name TEXT,
            first_name TEXT, business_name TEXT
        );
    """)
    conn.execute(
        "INSERT INTO whatsmeow_lid_map (pn, lid) VALUES (?, ?)",
        ("13232432100", "231241139937355"),
    )
    conn.execute(
        "INSERT INTO whatsmeow_contacts (their_jid, full_name) VALUES (?, ?)",
        ("13232432100@s.whatsapp.net", "Alice Wonderland"),
    )
    conn.commit()
    conn.close()
    return db_path
