import json
import logging

from pydantic_ai import RunContext

from client import bridge, db
from tools.deps import AgentDeps

logger = logging.getLogger(__name__)


def search_messages(
    ctx: RunContext[AgentDeps],
    search: str | None = None,
    chat_jid: str | None = None,
    sender_phone_number: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 25,
    page: int = 0,
    sort_by: str = "newest",
) -> str:
    """Search or browse WhatsApp messages.

    Use this for any message query — from simple "show me the latest
    messages" (call with no filters) to targeted searches like "messages
    about X in the gardening group from last week". All filters are
    optional and combine with AND.

    Args:
        search: Text to search for in message content (case-insensitive).
        chat_jid: Filter to a specific chat by its JID (e.g. "12345@g.us").
        sender_phone_number: Filter by sender's phone number (e.g. "972501234567").
        after: ISO-8601 timestamp — only return messages after this time.
        before: ISO-8601 timestamp — only return messages before this time.
        limit: Maximum number of messages to return (default 25).
        page: Page number for pagination, starting at 0.
        sort_by: "newest" (default) or "oldest".

    Returns:
        JSON array of message objects matching the criteria, each with
        id, timestamp, sender, content, chat_name, chat_jid, is_from_me,
        and media_type fields.
    """
    logger.debug("Tool: search_messages → db.get_messages(search=%s, chat=%s, sender=%s, after=%s, before=%s, limit=%d, page=%d, sort_by=%s)", search, chat_jid, sender_phone_number, after, before, limit, page, sort_by)
    messages = db.get_messages(
        ctx.deps.conn,
        search=search,
        chat_jid=chat_jid,
        sender_phone_number=sender_phone_number,
        after=after,
        before=before,
        limit=limit,
        page=page,
        sort_by=sort_by,
    )
    logger.debug("  → %d messages returned", len(messages))
    return json.dumps([msg.model_dump(mode="json") for msg in messages], ensure_ascii=False)


def get_message_context(
    ctx: RunContext[AgentDeps],
    message_id: str,
    before: int = 5,
    after: int = 5,
) -> str:
    """Get a specific message and the conversation around it.

    Use this when the user asks "show me message X with context" or
    "what was said before/after this message?". Returns the target
    message plus a window of surrounding messages in the same chat.

    Args:
        message_id: The unique ID of the message to center on.
        before: Number of messages before the target to include (default 5).
        after: Number of messages after the target to include (default 5).

    Returns:
        JSON object with "message" (the target), "before" (list of
        preceding messages), and "after" (list of following messages).
    """
    logger.debug("Tool: get_message_context → db.get_message_context(id=%s, before=%d, after=%d)", message_id, before, after)
    context = db.get_message_context(ctx.deps.conn, message_id=message_id, before=before, after=after)
    logger.debug("  → %d before, %d after", len(context.before), len(context.after))
    return json.dumps({
        "message": context.message.model_dump(mode="json"),
        "before": [m.model_dump(mode="json") for m in context.before],
        "after": [m.model_dump(mode="json") for m in context.after],
    }, ensure_ascii=False)


def search_chats(
    ctx: RunContext[AgentDeps],
    search: str | None = None,
    exclude_groups: bool = False,
    sort_by: str = "last_active",
    limit: int = 100,
    page: int = 0,
) -> str:
    """Find chats or groups by name or JID.

    Use this when the user asks "find the gardening group", "what chats
    do I have?", "show me my groups", or "find a chat with X". Can
    exclude group chats to only show private conversations.

    Args:
        search: Text to search for in chat name or JID.
        exclude_groups: If True, exclude group chats (ending in @g.us).
        sort_by: "last_active" (default) or "name".
        limit: Maximum number of chats to return (default 100).
        page: Page number for pagination, starting at 0.

    Returns:
        JSON array of chat objects with jid, name, last_message_time,
        last_message, last_sender, and last_is_from_me fields.
    """
    logger.debug("Tool: search_chats → db.get_chats(search=%s, exclude_groups=%s, sort_by=%s, limit=%d, page=%d)", search, exclude_groups, sort_by, limit, page)
    chats = db.get_chats(
        ctx.deps.conn,
        search=search,
        exclude_groups=exclude_groups,
        sort_by=sort_by,
        limit=limit,
        page=page,
    )
    logger.debug("  → %d chats returned", len(chats))
    return json.dumps([chat.model_dump(mode="json") for chat in chats], ensure_ascii=False)


def get_contact_chats(
    ctx: RunContext[AgentDeps],
    contact: str,
    limit: int = 100,
    page: int = 0,
) -> str:
    """Find all chats that a specific contact participates in.

    Use this when the user asks "which groups is X in?" or wants to
    see everywhere a particular person has sent messages. Accepts a
    phone number (e.g. "972501234567"), JID, or LID.

    Args:
        contact: Phone number, JID, or LID of the contact to look up.
        limit: Maximum number of chats to return (default 100).
        page: Page number for pagination, starting at 0.

    Returns:
        JSON array of chat objects where the contact has sent messages,
        sorted by most recently active first.
    """
    logger.debug("Tool: get_contact_chats → db.get_contact_chats(contact=%s, limit=%d, page=%d)", contact, limit, page)
    chats = db.get_contact_chats(ctx.deps.conn, contact=contact, limit=limit, page=page)
    logger.debug("  → %d chats returned", len(chats))
    return json.dumps([chat.model_dump(mode="json") for chat in chats], ensure_ascii=False)


def search_contacts(ctx: RunContext[AgentDeps], search: str) -> str:
    """Search for contacts by name or phone number.

    Use this when the user asks "who is John?" or "what's the number
    for X?". Returns matching contacts with their JID, display name,
    and phone number.

    Args:
        search: Name or phone number to search for.

    Returns:
        JSON array of contact objects with jid, name, and phone fields.
    """
    logger.debug("Tool: search_contacts → db.get_contacts(search=%s)", search)
    contacts = db.get_contacts(ctx.deps.conn, search=search)
    logger.debug("  → %d contacts returned", len(contacts))
    return json.dumps([contact.model_dump(mode="json") for contact in contacts], ensure_ascii=False)


def get_active_contacts(
    ctx: RunContext[AgentDeps],
    chat_jid: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 25,
) -> str:
    """Get the most active contacts ranked by message count.

    Use this when the user asks "who's most active?", "who talks the
    most in this group?", or wants a ranked list of frequent senders.
    Can be filtered to a specific chat and time range.

    Args:
        chat_jid: Filter to a specific chat JID (only count messages there).
        after: ISO-8601 timestamp — only count messages after this time.
        before: ISO-8601 timestamp — only count messages before this time.
        limit: Maximum number of contacts to return (default 25).

    Returns:
        JSON array of contact objects ranked by message_count descending.
        Each contact has jid, name, phone, and message_count fields.
    """
    logger.debug("Tool: get_active_contacts → db.get_active_contacts(chat=%s, after=%s, before=%s, limit=%d)", chat_jid, after, before, limit)
    contacts = db.get_active_contacts(
        ctx.deps.conn,
        chat_jid=chat_jid,
        after=after,
        before=before,
        limit=limit,
    )
    logger.debug("  → %d contacts returned", len(contacts))
    return json.dumps([contact.model_dump(mode="json") for contact in contacts], ensure_ascii=False)


def sync_and_report(
    ctx: RunContext[AgentDeps],
    idle_timeout: int = 15,
    max_duration: int = 300,
) -> str:
    """Connect to WhatsApp and pull new messages.

    Runs the bridge to sync messages, then returns only truly new messages
    (those with timestamps after the newest message already in the database).
    Historic backfill messages pulled by the bridge are separated out —
    ignore historic_messages for summarization, focus on messages and chats.

    Args:
        idle_timeout: Seconds of inactivity before batch sync completes (default 15).
        max_duration: Absolute max seconds for batch sync (default 300).

    Returns:
        JSON object with success, total_new_messages, fresh_message_count,
        historic_message_count, chats (grouped fresh messages with counts),
        messages (fresh messages), historic_messages (backfill, skip these for summary),
        bridge_output, and bridge_return_code.
    """
    logger.debug("Tool: sync_and_report(idle_timeout=%d, max_duration=%d)", idle_timeout, max_duration)
    result = bridge.sync(idle_timeout=idle_timeout, max_duration=max_duration)
    return json.dumps(result, ensure_ascii=False)

