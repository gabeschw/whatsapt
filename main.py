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
        instructions=(
            "You are a WhatsApp assistant. Tools return JSON-formatted data — "
            "format it clearly when displaying to the user. Be concise."
        ),
    )
    agent.tool(search_messages)
    agent.tool(get_message_context)
    agent.tool(search_chats)
    agent.tool(get_contact_chats)
    agent.tool(search_contacts)
    agent.tool(get_active_contacts)
    agent.tool(sync_and_report)

    history = []
    print("WhatsApt Chatbot is ready! Type /exit or ctrl+c to quit.\n")

    try:
        while True:
            try:
                prompt = input("> ").strip()
            except EOFError:
                break

            if not prompt:
                continue
            if prompt.lower() in ("/exit", "/quit"):
                break

            result = agent.run_sync(prompt, deps=deps, message_history=history)
            history = result.all_messages()
            print(f"\n{result.output}")
    except KeyboardInterrupt:
        pass
    finally:
        print("\nBye!")


if __name__ == "__main__":
    main()
