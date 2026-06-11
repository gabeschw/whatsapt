import logging
import os

from pydantic_ai import Agent
from tools.deps import AgentDeps
from tools.queries import get_recent_messages, sync_and_report

from client import db

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")


def main():
    deps = AgentDeps(conn=db.connect())
    agent = Agent(
        os.getenv("LLM_MODEL", "openrouter:openrouter/free"),
        deps_type=AgentDeps,
        instructions="You are a WhatsApp assistant. Tools return JSON-formatted message data — format it nicely when displaying to the user.",
    )
    agent.tool(get_recent_messages)
    agent.tool(sync_and_report)

    result = agent.run_sync("Sync and summarize the new messages", deps=deps)
    print(result.output)


if __name__ == "__main__":
    main()
