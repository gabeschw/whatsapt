import sqlite3
from unittest.mock import patch

import pytest

import client.db
from client.db import (
    connect,
    get_chats,
    get_contact_chats,
    get_message_context,
    get_messages,
    get_sender_name,
    get_contacts,
    get_active_contacts,
)


def test_connect_sets_row_factory():
    conn = connect(":memory:")
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_get_messages_default_limit(db):
    rows = get_messages(db)
    assert len(rows) <= 25


def test_get_messages_custom_limit(db):
    rows = get_messages(db, limit=3)
    assert len(rows) == 3


def test_get_messages_chat_filter(db):
    rows = get_messages(db, chat_jid="jid-1")
    assert len(rows) == 5
    for row in rows:
        assert row.chat_jid == "jid-1"


def test_get_messages_sort_oldest(db):
    rows = get_messages(db, limit=5, sort_by="oldest")
    timestamps = [r.timestamp for r in rows]
    assert timestamps == sorted(timestamps)


def test_get_messages_empty_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE messages ("
        "id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP, "
        "is_from_me BOOLEAN, media_type TEXT, filename TEXT, url TEXT, "
        "media_key BLOB, file_sha256 BLOB, file_enc_sha256 BLOB, "
        "file_length INTEGER, deleted_at TIMESTAMP, inserted_at TIMESTAMP, "
        "quoted_message_id TEXT"
        ")"
    )
    conn.execute("CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP)")
    rows = get_messages(conn)
    assert rows == []
    conn.close()


def test_get_messages_search(db):
    rows = get_messages(db, search="Hello")
    assert len(rows) == 1
    assert rows[0].id == "msg-1"


def test_get_messages_after(db):
    rows = get_messages(db, after="2024-01-03T00:00:00")
    assert len(rows) == 3


def test_get_messages_before(db):
    rows = get_messages(db, before="2024-01-02T00:00:00")
    assert len(rows) == 5


def test_get_messages_pagination(db):
    page0 = get_messages(db, limit=3, page=0, sort_by="oldest")
    page1 = get_messages(db, limit=3, page=1, sort_by="oldest")
    assert len(page0) == 3
    assert len(page1) == 3
    assert [r.id for r in page0] != [r.id for r in page1]


def test_get_message_found(db):
    rows = get_messages(db, message_id="msg-3")
    assert len(rows) == 1
    assert rows[0].id == "msg-3"
    assert rows[0].content == "Hi there"


def test_get_message_not_found(db):
    assert get_messages(db, message_id="msg-none") == []


def test_get_message_has_chat_name(db):
    rows = get_messages(db, message_id="msg-1")
    assert rows[0].chat_name == "Group Chat 1"


def test_get_message_context_with_surrounding(db):
    ctx = get_message_context(db, "msg-3")
    assert ctx.message.id == "msg-3"
    assert len(ctx.before) == 1
    assert ctx.before[0].id == "msg-1"
    assert len(ctx.after) == 3
    assert [r.id for r in ctx.after] == ["msg-4", "msg-9", "msg-10"]


def test_get_message_context_not_found(db):
    with pytest.raises(ValueError, match="not found"):
        get_message_context(db, "msg-none")


def test_get_message_context_custom_window(db):
    ctx = get_message_context(db, "msg-4", before=0, after=0)
    assert ctx.message.id == "msg-4"
    assert len(ctx.before) == 0
    assert len(ctx.after) == 0


def test_get_chats_default(db):
    chats = get_chats(db)
    assert len(chats) == 3
    assert all(isinstance(c.jid, str) for c in chats)


def test_get_chats_sort_by_last_active(db):
    chats = get_chats(db, sort_by="last_active")
    assert chats[0].jid == "jid-3"


def test_get_chats_sort_by_name(db):
    chats = get_chats(db, sort_by="name")
    assert chats[0].jid == "jid-1"


def test_get_chats_with_search(db):
    chats = get_chats(db, search="Group Chat 1")
    assert len(chats) == 1
    assert chats[0].jid == "jid-1"


def test_get_chats_include_last_message(db):
    chats = get_chats(db, include_last_message=True)
    jid1 = next(c for c in chats if c.jid == "jid-1")
    assert jid1.last_message == "Doing great!"
    assert jid1.last_sender == "Alice"


def test_get_chats_no_last_message(db):
    chats = get_chats(db, include_last_message=False)
    jid1 = next(c for c in chats if c.jid == "jid-1")
    assert jid1.last_message is None


def test_get_chats_pagination(db):
    page0 = get_chats(db, limit=2, page=0, sort_by="name")
    page1 = get_chats(db, limit=2, page=1, sort_by="name")
    assert len(page0) == 2
    assert len(page1) == 1
    assert page0[0].jid != page1[0].jid


def test_get_chat_found(db):
    chats = get_chats(db, chat_jid="jid-1")
    assert len(chats) == 1
    assert chats[0].name == "Group Chat 1"
    assert chats[0].last_message == "Doing great!"


def test_get_chat_not_found(db):
    assert get_chats(db, chat_jid="jid-none") == []


def test_get_contact_chats_by_sender(db):
    chats = get_contact_chats(db, "Alice")
    assert len(chats) == 1
    assert chats[0].jid == "jid-1"


def test_get_contact_chats_no_match(db):
    chats = get_contact_chats(db, "Nobody")
    assert chats == []


def test_get_direct_chat_found(db):
    chats = get_chats(db, search="jid-1", exclude_groups=True)
    assert len(chats) == 1
    assert chats[0].jid == "jid-1"


def test_get_direct_chat_not_found(db):
    assert get_chats(db, search="nonexistent", exclude_groups=True) == []


def test_get_direct_chat_excludes_groups(db):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE messages (
            id TEXT, chat_jid TEXT, sender TEXT, content TEXT,
            timestamp TIMESTAMP, is_from_me BOOLEAN
        );
        CREATE TABLE chats (
            jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP
        );
    """)
    conn.execute("INSERT INTO chats (jid, name) VALUES (?, ?)", ("12345-67890@g.us", "Group Chat"))
    conn.execute("INSERT INTO chats (jid, name) VALUES (?, ?)", ("12345@s.whatsapp.net", "Direct Chat"))
    conn.commit()

    chats = get_chats(conn, search="12345", exclude_groups=True)
    assert len(chats) == 1
    assert "@g.us" not in chats[0].jid
    conn.close()


def test_get_contacts_by_name(db):
    contacts = get_contacts(db, "Group")
    assert len(contacts) == 3


def test_get_contacts_by_jid(db):
    contacts = get_contacts(db, "jid-2")
    assert len(contacts) == 1
    assert contacts[0].jid == "jid-2"


def test_get_contacts_no_match(db):
    contacts = get_contacts(db, "zzzznotfound")
    assert contacts == []


def test_get_contacts_excludes_groups(db):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP)"
    )
    conn.execute("INSERT INTO chats (jid, name) VALUES (?, ?)", ("12345-67890@g.us", "Group"))
    conn.execute("INSERT INTO chats (jid, name) VALUES (?, ?)", ("12345@s.whatsapp.net", "Alice"))
    conn.commit()

    contacts = get_contacts(conn, "12345")
    assert len(contacts) == 1
    assert contacts[0].jid == "12345@s.whatsapp.net"
    conn.close()


def test_get_active_contacts(db):
    contacts = get_active_contacts(db)
    assert len(contacts) == 5
    assert contacts[0].message_count is not None
    assert contacts[0].message_count >= contacts[1].message_count


def test_get_active_contacts_limit(db):
    contacts = get_active_contacts(db, limit=2)
    assert len(contacts) == 2


def test_get_active_contacts_chat_filter(db):
    contacts = get_active_contacts(db, chat_jid="jid-1")
    assert len(contacts) == 2
    assert all(c.message_count is not None for c in contacts)


def test_get_active_contacts_after(db):
    contacts = get_active_contacts(db, after="2024-01-03T00:00:00")
    assert len(contacts) == 3


def test_get_active_contacts_before(db):
    contacts = get_active_contacts(db, before="2024-01-02T00:00:00")
    assert len(contacts) == 3


def test_get_sender_name_from_chats(db):
    name = get_sender_name(db, "jid-1@s.whatsapp.net")
    assert name == "Group Chat 1"


def test_get_sender_name_fallback(db):
    name = get_sender_name(db, "unknown@s.whatsapp.net")
    assert name == "unknown@s.whatsapp.net"


def test_get_sender_name_bare_phone(db):
    name = get_sender_name(db, "jid-1")
    assert name == "Group Chat 1"


def test_get_sender_name_skips_numeric(db):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP)"
    )
    conn.execute("INSERT INTO chats (jid, name) VALUES (?, ?)", ("5551234@s.whatsapp.net", "5551234"))
    conn.commit()

    name = get_sender_name(conn, "5551234@s.whatsapp.net")
    assert name == "5551234@s.whatsapp.net"
    conn.close()


def test_sender_aliases_with_lid_map(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        result = client.db._sender_aliases("13232432100")
    expected = [
        "13232432100", "13232432100@s.whatsapp.net",
        "231241139937355", "231241139937355@lid",
    ]
    assert sorted(result) == sorted(expected)


def test_sender_aliases_from_lid(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        result = client.db._sender_aliases("231241139937355")
    expected = [
        "13232432100", "13232432100@s.whatsapp.net",
        "231241139937355", "231241139937355@lid",
    ]
    assert sorted(result) == sorted(expected)


def test_sender_aliases_no_mapping(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        result = client.db._sender_aliases("99999999999")
    expected = ["99999999999", "99999999999@s.whatsapp.net", "99999999999@lid"]
    assert sorted(result) == sorted(expected)


def test_sender_aliases_with_jid_suffix():
    result = client.db._sender_aliases("13232432100@s.whatsapp.net")
    expected = ["13232432100", "13232432100@s.whatsapp.net", "13232432100@lid"]
    assert sorted(result) == sorted(expected)


def test_resolve_lid_to_phone_found(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_lid_to_phone("231241139937355") == "13232432100"


def test_resolve_lid_to_phone_from_jid(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_lid_to_phone("231241139937355@lid") == "13232432100"


def test_resolve_lid_to_phone_not_found(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_lid_to_phone("99999999999") is None


def test_resolve_name_found(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_name_from_whatsmeow("13232432100@s.whatsapp.net") == "Alice Wonderland"


def test_resolve_name_not_found(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_name_from_whatsmeow("99999999999@s.whatsapp.net") is None


def test_resolve_name_from_lid(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_name_from_whatsmeow("231241139937355@lid") == "Alice Wonderland"


def test_resolve_name_lid_not_in_map(whatsmeow_db_path):
    with patch.object(client.db, "WHATSAPP_DB_PATH", whatsmeow_db_path):
        assert client.db._resolve_name_from_whatsmeow("99999999999@lid") is None
