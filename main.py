import logging
import os

from pydantic_ai import Agent
from tools.deps import AgentDeps
from tools.queries import (
    get_active_contacts,
    get_contact_chats,
    get_message_context,
    search_chats,
    search_contacts,
    search_messages,
    sync_and_report,
)

from client import db

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")


def main():
    deps = AgentDeps(conn=db.connect())
    agent = Agent(
        os.getenv("LLM_MODEL", "openrouter:openrouter/free"),
        deps_type=AgentDeps,
        instructions="You are a WhatsApp assistant. Tools return JSON-formatted message data — format it nicely when displaying to the user.",
    )
    agent.tool(search_messages)
    agent.tool(get_message_context)
    agent.tool(search_chats)
    agent.tool(get_contact_chats)
    agent.tool(search_contacts)
    agent.tool(get_active_contacts)
    agent.tool(sync_and_report)

    result = agent.run_sync("What are the latest messages?", deps=deps)
    print(result.output)


if __name__ == "__main__":
    main()
