import json
import logging

from pydantic_ai import RunContext

from client import bridge, db
from tools.deps import AgentDeps

logger = logging.getLogger(__name__)


def get_recent_messages(ctx: RunContext[AgentDeps], limit: int = 10) -> str:
    """Fetch recent WhatsApp messages from the database, returned as JSON.

    Args:
        limit: Maximum number of messages to fetch (default 10).
    """
    logger.info("Tool: get_recent_messages(limit=%d)", limit)
    messages = db.get_messages(ctx.deps.conn, limit=limit)
    return json.dumps([msg.model_dump(mode="json") for msg in messages], ensure_ascii=False)


def sync_and_report(
    ctx: RunContext[AgentDeps],
    idle_timeout: int = 15,
    max_duration: int = 300,
) -> str:
    """Run the WhatsApp bridge in batch mode and return new messages.

    Connects to WhatsApp, collects new messages until idle, then returns
    messages inserted since the last sync, grouped by chat.

    Args:
        idle_timeout: Seconds of inactivity before batch sync completes (default 15).
        max_duration: Absolute max seconds for batch sync (default 300).
    """
    logger.info("Tool: sync_and_report(idle_timeout=%d, max_duration=%d)", idle_timeout, max_duration)
    result = bridge.sync(idle_timeout=idle_timeout, max_duration=max_duration)
    return json.dumps(result, ensure_ascii=False)

