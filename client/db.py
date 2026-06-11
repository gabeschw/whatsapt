import datetime
import os
import sqlite3

from client.models import Chat, Contact, Message, MessageContext

sqlite3.register_adapter(datetime.datetime, lambda val: val.isoformat())

MESSAGES_DB_PATH = os.getenv("MESSAGES_DB_PATH", "messages.db")
WHATSAPP_DB_PATH = os.getenv("WHATSAPP_DB_PATH", "whatsapp.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    Args:
        db_path: Path to the database file. Falls back to MESSAGES_DB_PATH env var.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    path = db_path or MESSAGES_DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)  # type: ignore
    conn.row_factory = sqlite3.Row
    return conn


# Helper functions

def _whatsmeow_query(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Execute a single-row query on the whatsmeow DB. Returns first row or None."""
    if not WHATSAPP_DB_PATH or not os.path.isfile(WHATSAPP_DB_PATH):
        return None
    try:
        conn = connect(WHATSAPP_DB_PATH)
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None

def _sender_aliases(value: str) -> list[str]:
    """Return all possible sender formats.
    
    messages.sender is written inconsistently: the same contact may appear as
    bare phone ("13232432100"), full phone JID ("13232432100@s.whatsapp.net"),
    bare LID ("231241139937355"), or full LID JID ("231241139937355@lid").
    whatsmeow_lid_map (whatsapp.db) maps pn<->lid; we emit all four forms so
    an IN-based filter catches every row regardless of which form was stored.
    """
    bare = value.split("@")[0]
    pn = None
    lid = None
    row = _whatsmeow_query("SELECT lid FROM whatsmeow_lid_map WHERE pn = ?", (bare,))
    if row:
        pn, lid = bare, row["lid"]
    else:
        row = _whatsmeow_query("SELECT pn FROM whatsmeow_lid_map WHERE lid = ?", (bare,))
        if row:
            pn, lid = row["pn"], bare
    aliases = []
    if pn:
        aliases += [pn, f"{pn}@s.whatsapp.net"]
    if lid:
        aliases += [lid, f"{lid}@lid"]
    if not aliases:
        # No mapping found; emit the bare form plus both possible suffixes so
        # we still match whichever form the bridge happened to store.
        aliases = [bare, f"{bare}@s.whatsapp.net", f"{bare}@lid"]
    return aliases


def _resolve_lid_to_phone(lid_or_jid: str) -> str | None:
    """Resolve a WhatsApp LID (linked device identifier) to a phone number.

    WhatsApp's newer protocol uses opaque LIDs (e.g. '35047067385985') as sender
    identifiers instead of phone numbers. The whatsmeow_lid_map table maps these
    back to real phone numbers.

    Returns the phone number if found, None otherwise.
    """
    # Extract the numeric part from JID-style strings (e.g. '35047067385985@lid')
    lid = lid_or_jid.split("@")[0]
    row = _whatsmeow_query("SELECT pn FROM whatsmeow_lid_map WHERE lid = ? LIMIT 1", (lid,))
    return row["pn"] if row else None


def _resolve_name_from_whatsmeow(jid: str) -> str | None:
    """Look up a contact name from whatsmeow's contact store (whatsapp.db).

    Handles both standard JIDs (12345@s.whatsapp.net) and LIDs (opaque numeric
    identifiers used by WhatsApp's linked device protocol). LIDs are first
    resolved to phone numbers via whatsmeow_lid_map, then looked up in contacts.

    Falls back gracefully if the DB or table doesn't exist.
    """
    lookup_jid = jid
    jid_prefix = jid.split("@")[0]
    jid_suffix = jid.split("@")[1] if "@" in jid else ""

    # If this is a LID (@lid suffix) or a raw number, try LID map first.
    # LIDs overlap in length with phone numbers (12-15 digits) so we always
    # attempt LID resolution and fall through to direct contact lookup if not found.
    if jid_suffix in ("lid", ""):
        phone = _resolve_lid_to_phone(jid_prefix)
        if phone:
            lookup_jid = phone + "@s.whatsapp.net"
        elif jid_suffix == "lid":
            # Definitely a LID but not in the map — can't resolve
            return None

    row = _whatsmeow_query(
        "SELECT full_name, push_name, first_name, business_name FROM whatsmeow_contacts WHERE their_jid = ? LIMIT 1",
        (lookup_jid,),
    )
    if row:
        return row["full_name"] or row["push_name"] or row["first_name"] or row["business_name"] or None
    return None


## Queries

def get_sender_name(conn: sqlite3.Connection, sender_jid: str) -> str:
    """Resolve a sender JID to a display name.

    Checks the chats table first (messages.db), then falls back to the
    whatsmeow contact store (whatsapp.db). Returns the JID itself if
    no name is found.

    Args:
        sender_jid: The JID of the sender (e.g. "12345@s.whatsapp.net").

    Returns:
        Display name if found, or the original JID as fallback.
    """
    # Extract phone number from whatever JID form we received
    phone = sender_jid.split("@")[0]

    # Try chats table — a single LIKE query catches both bare phone and full JID.
    # Names that are phone numbers (all digits) are skipped — they're not useful
    row = conn.execute(
        "SELECT name FROM chats WHERE jid LIKE ? LIMIT 1",
        (f"%{phone}%",),
    ).fetchone()
    if row and row["name"] and not row["name"].replace("+", "").isdigit():
        return row["name"]

    # Fall back to whatsmeow contact store
    whatsmeow_name = _resolve_name_from_whatsmeow(sender_jid)
    if whatsmeow_name:
        return whatsmeow_name
    if "@" not in sender_jid:
        whatsmeow_name = _resolve_name_from_whatsmeow(sender_jid + "@s.whatsapp.net")
        if whatsmeow_name:
            return whatsmeow_name
    return sender_jid


def get_messages(
    conn: sqlite3.Connection,
    after: str | None = None,
    before: str | None = None,
    after_inserted_at: str | None = None,
    sender_phone_number: str | None = None,
    chat_jid: str | None = None,
    search: str | None = None,
    limit: int = 25,
    page: int = 0,
    sort_by: str = "newest",
) -> list[Message]:
    """Get messages matching the specified criteria with optional context.

    Args:
        after: Optional ISO-8601 formatted string to only return messages after this date
        before: Optional ISO-8601 formatted string to only return messages before this date
        after_inserted_at: Only return messages whose inserted_at is greater than this value (ISO-8601 format)
        sender_phone_number: Optional phone number to filter messages by sender
        chat_jid: Optional chat JID to filter messages by chat
        search: Optional search term to filter messages by content
        limit: Maximum number of messages to return (default 25)
        page: Page number for pagination (default 0)
        sort_by: Sort order - "newest" (default) or "oldest" for chronological ordering

    Returns:
        List of Messages matching the criteria.
    """
    query = ["SELECT messages.*, chats.name as chat_name FROM messages JOIN chats ON messages.chat_jid = chats.jid",]
    where = []
    params = []

    if after:
        where.append("messages.timestamp >= ?")
        params.append(after)
    if before:
        where.append("messages.timestamp <= ?")
        params.append(before)
    if after_inserted_at:
        where.append("messages.inserted_at >= ?")
        params.append(after_inserted_at)
    if sender_phone_number:
        aliases = _sender_aliases(sender_phone_number)
        where.append(f"messages.sender IN ({','.join('?' * len(aliases))})")
        params.extend(aliases)
    if chat_jid:
        where.append("messages.chat_jid = ?")
        params.append(chat_jid)
    if search:
        where.append("(instr(LOWER(messages.content), LOWER(?)) > 0 OR instr(messages.content, ?) > 0)")
        params.extend([search, search])

    if where:
        query.append("WHERE " + " AND ".join(where))

    order = "DESC" if sort_by == "newest" else "ASC"
    offset = page * limit
    query.append(f"ORDER BY messages.timestamp {order} LIMIT ? OFFSET ?")
    params.extend([limit, offset])

    rows = conn.execute(" ".join(query), params).fetchall()
    return [Message(**row) for row in rows]



def get_message(conn: sqlite3.Connection, message_id: str) -> Message | None:
    """Get a single message by its ID.

    Args:
        message_id: The unique ID of the message.

    Returns:
        Message object if found, None otherwise.
    """
    row = conn.execute(
        "SELECT messages.*, chats.name as chat_name FROM messages "
        "JOIN chats ON messages.chat_jid = chats.jid WHERE messages.id = ?",
        (message_id,),
    ).fetchone()
    return Message(**row) if row else None


def get_message_context(
    conn: sqlite3.Connection,
    message_id: str,
    before: int = 5,
    after: int = 5,
) -> MessageContext:
    """Get a message and its surrounding context in the same chat.

    Args:
        message_id: The unique ID of the target message.
        before: Number of messages before the target to include (default 5).
        after: Number of messages after the target to include (default 5).

    Returns:
        MessageContext containing the target message with surrounding messages.

    Raises:
        ValueError: If no message with the given ID exists.
    """
    row = conn.execute(
        "SELECT messages.*, chats.name as chat_name FROM messages JOIN chats ON messages.chat_jid = chats.jid WHERE messages.id = ?",
        (message_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Message with ID {message_id} not found")
    target = Message(**row)

    before_rows = conn.execute(
        "SELECT messages.*, chats.name as chat_name FROM messages JOIN chats ON messages.chat_jid = chats.jid "
        "WHERE messages.chat_jid = ? AND messages.timestamp < ? "
        "ORDER BY messages.timestamp DESC LIMIT ?",
        (target.chat_jid, target.timestamp.isoformat(), before),
    ).fetchall()

    after_rows = conn.execute(
        "SELECT messages.*, chats.name as chat_name FROM messages JOIN chats ON messages.chat_jid = chats.jid "
        "WHERE messages.chat_jid = ? AND messages.timestamp > ? "
        "ORDER BY messages.timestamp ASC LIMIT ?",
        (target.chat_jid, target.timestamp.isoformat(), after),
    ).fetchall()

    return MessageContext(
        message=target,
        before=[Message(**r) for r in before_rows],
        after=[Message(**r) for r in after_rows],
    )

def get_chats(
    conn: sqlite3.Connection,
    search: str | None = None,
    limit: int = 100,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active",
) -> list[Chat]:
    """Get all chats with optional name search.

    Args:
        search: Optional search term to filter chats by name or JID.
        limit: Maximum number of chats to return (default 100).
        page: Page number for pagination (default 0).
        include_last_message: Whether to include the last message for each chat (default True).
        sort_by: Sort order — "last_active" (default) or "name".

    Returns:
        List of Chat objects matching the criteria.
    """
    last_msg_cols = (
        "m.content as last_message, m.sender as last_sender, m.is_from_me as last_is_from_me"
        if include_last_message
        else "NULL as last_message, NULL as last_sender, NULL as last_is_from_me"
    )
    query = [f"SELECT c.jid, c.name, c.last_message_time, {last_msg_cols} FROM chats c"]
    if include_last_message:
        query.append("LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp")

    params = []
    if search:
        query.append("WHERE (instr(LOWER(c.name), LOWER(?)) > 0 OR instr(c.name, ?) > 0 OR c.jid LIKE ?)")
        params.extend([search, search, f"%{search}%"])

    order = "c.last_message_time DESC" if sort_by == "last_active" else "c.name"
    offset = page * limit
    query.append(f"ORDER BY {order} LIMIT ? OFFSET ?")
    params.extend([limit, offset])

    rows = conn.execute(" ".join(query), params).fetchall()
    return [Chat(**row) for row in rows]


def get_chat(conn: sqlite3.Connection, chat_jid: str) -> Chat | None:
    """Get a single chat by its JID.

    Args:
        chat_jid: The full JID of the chat (e.g. "12345@s.whatsapp.net").

    Returns:
        Chat object if found, None otherwise.
    """
    row = conn.execute(
        """
        SELECT c.jid, c.name, c.last_message_time,
               m.content as last_message, m.sender as last_sender, m.is_from_me as last_is_from_me
        FROM chats c
        LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp
        WHERE c.jid = ?
        """,
        (chat_jid,),
    ).fetchone()
    return Chat(**row) if row else None


def get_contact_chats(
    conn: sqlite3.Connection,
    contact: str,
    limit: int = 100,
    page: int = 0,
) -> list[Chat]:
    """Get all chats that involve a specific contact.

    Args:
        contact: Phone number, JID, or LID of the contact.
        limit: Maximum number of chats to return (default 100).
        page: Page number for pagination (default 0).

    Returns:
        List of Chat objects where the contact has sent a message.
    """
    aliases = _sender_aliases(contact)
    placeholders = ",".join("?" * len(aliases))
    rows = conn.execute(
        f"""
        SELECT DISTINCT c.jid, c.name, c.last_message_time,
               last_msg.content as last_message, last_msg.sender as last_sender,
               last_msg.is_from_me as last_is_from_me
        FROM chats c
        LEFT JOIN messages last_msg ON c.jid = last_msg.chat_jid AND c.last_message_time = last_msg.timestamp
        WHERE EXISTS (
            SELECT 1 FROM messages contact_msg
            WHERE contact_msg.chat_jid = c.jid AND contact_msg.sender IN ({placeholders})
        )
        ORDER BY c.last_message_time DESC LIMIT ? OFFSET ?
        """,
        (*aliases, limit, page * limit),
    ).fetchall()
    return [Chat(**row) for row in rows]


def get_direct_chat_by_contact(conn: sqlite3.Connection, phone: str) -> Chat | None:
    """Get the private (non-group) chat for a contact by phone number.

    Args:
        phone: Phone number to search for (bare or with prefix).

    Returns:
        Chat object if a matching private chat is found, None otherwise.
    """
    row = conn.execute(
        """
        SELECT c.jid, c.name, c.last_message_time,
               m.content as last_message, m.sender as last_sender, m.is_from_me as last_is_from_me
        FROM chats c
        LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp
        WHERE c.jid LIKE ? AND c.jid NOT LIKE '%@g.us'
        LIMIT 1
        """,
        (f"%{phone}%",),
    ).fetchone()
    return Chat(**row) if row else None


def get_contacts(conn: sqlite3.Connection, search: str) -> list[Contact]:
    """Search for contacts by name or JID.

    Args:
        search: Search term to match against name or JID.

    Returns:
        List of Contact objects matching the search term.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT jid, name FROM chats
        WHERE (instr(LOWER(name), LOWER(?)) > 0 OR instr(name, ?) > 0 OR jid LIKE ?)
          AND jid NOT LIKE '%@g.us'
        ORDER BY name, jid LIMIT 50
        """,
        (search, search, f"%{search}%"),
    ).fetchall()
    return [Contact(jid=r["jid"], name=r["name"], phone=r["jid"].split("@")[0]) for r in rows]


def get_most_active_contacts(
    conn: sqlite3.Connection,
    after: str | None = None,
    before: str | None = None,
    chat_jid: str | None = None,
    limit: int = 25,
) -> list[Contact]:
    """Get contacts ranked by message count, with optional time and chat filters.

    Args:
        after: Optional ISO-8601 formatted string to only count messages after this date.
        before: Optional ISO-8601 formatted string to only count messages before this date.
        chat_jid: Optional chat JID to scope the query to a specific chat.
        limit: Maximum number of contacts to return (default 25).

    Returns:
        List of Contact objects ordered by message_count descending.
    """
    query = ["SELECT m.sender as jid, c.name, COUNT(*) as message_count FROM messages m"]
    query.append("LEFT JOIN chats c ON m.chat_jid = c.jid")
    where = []
    params: list = []

    if chat_jid:
        where.append("m.chat_jid = ?")
        params.append(chat_jid)
    if after:
        where.append("m.timestamp >= ?")
        params.append(after)
    if before:
        where.append("m.timestamp <= ?")
        params.append(before)

    if where:
        query.append("WHERE " + " AND ".join(where))

    query.append("GROUP BY m.sender ORDER BY message_count DESC LIMIT ?")
    params.append(limit)

    rows = conn.execute(" ".join(query), params).fetchall()
    return [Contact(jid=r["jid"], name=r["name"], phone=r["jid"].split("@")[0], message_count=r["message_count"]) for r in rows]
