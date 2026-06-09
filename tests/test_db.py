import sqlite3

from client.db import connect, print_messages, recent_messages


def test_connect_sets_row_factory():
    conn = connect(":memory:")
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_recent_messages_default_limit(db):
    rows = recent_messages(db)
    assert len(rows) == 5


def test_recent_messages_custom_limit(db):
    rows = recent_messages(db, n=3)
    assert len(rows) == 3


def test_recent_messages_chat_filter(db):
    rows = recent_messages(db, chat_jid="jid-1")
    assert len(rows) == 5
    for row in rows:
        assert row["chat_jid"] == "jid-1"


def test_recent_messages_empty_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE messages (chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP)"
    )
    rows = recent_messages(conn)
    assert rows == []
    conn.close()


def test_print_messages_chronological_order(capsys, db):
    rows = recent_messages(db, n=2, chat_jid="jid-1")
    print_messages(rows)
    out = capsys.readouterr().out
    assert "[2024-01-03 18:00] Bob:\nGood, you?\n" in out
    assert "[2024-01-03 18:01] Alice:\nDoing great!\n" in out


def test_print_messages_empty(capsys):
    print_messages([])
    assert capsys.readouterr().out.strip() == "No messages found."
