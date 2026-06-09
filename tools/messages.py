import json

from pydantic_ai import RunContext

from client.db import recent_messages
from tools.deps import AgentDeps


def get_recent_messages(ctx: RunContext[AgentDeps], limit: int = 10) -> str:
    """Fetch recent WhatsApp messages from the database, returned as JSON.
    
    Args:
        limit: Maximum number of messages to fetch (default 10).
    """
    messages = recent_messages(ctx.deps.db, limit)
    return json.dumps([msg.model_dump() for msg in messages], ensure_ascii=False)


