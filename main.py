import asyncio
import logging
import os

from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking
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


async def main():
    deps = AgentDeps(conn=db.connect())
    agent = Agent(
        os.getenv("LLM_MODEL", "openrouter:openrouter/free"),
        deps_type=AgentDeps,
        capabilities=[Thinking(effort='high')],
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

    ascii_art = open('ascii-art.txt').read()
    print(ascii_art)
    print("WhatsApt Chatbot is ready! Type /exit or ctrl+c to quit.\n")

    try:
        while True:
            try:
                prompt = (await asyncio.to_thread(input, "> ")).strip()
            except EOFError:
                break

            if not prompt:
                continue
            if prompt.lower() in ("/exit", "/quit"):
                break

            try:
                last_outputs = {}
                async with agent.run_stream(
                    prompt, deps=deps, message_history=history, retries=2
                ) as result:
                    async for response in result.stream_response():
                        for i, part in enumerate(response.parts):
                            if part.part_kind not in ('thinking', 'text'):
                                continue
                            key = (i, part.part_kind)
                            prev = last_outputs.get(key, "")
                            if part.content == prev:
                                continue
                            if part.content.startswith(prev):
                                delta = part.content[len(prev):]
                            else:
                                delta = part.content
                            if part.part_kind == 'thinking':
                                print(f"\033[2m{delta}\033[0m", end='', flush=True)
                            else:
                                print(delta, end='', flush=True)
                            last_outputs[key] = part.content
                    history = result.all_messages()
                    print()
            except Exception:
                print("\nModel request failed. Try again or switch models.")
    except KeyboardInterrupt:
        pass
    finally:
        print("\nBye!")


if __name__ == "__main__":
    asyncio.run(main())
