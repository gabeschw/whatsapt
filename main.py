import asyncio
import logging
import os

import click
import click_log

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
from tools.utility import get_current_time

from client import db

logger = logging.getLogger("whatsapt")

click_log.basic_config()

@click.command()
@click_log.simple_verbosity_option()
def cli():
    asyncio.run(_run_agent())


async def _run_agent():
    deps = AgentDeps(conn=db.connect())
    tools = [
        search_messages,
        get_message_context,
        search_chats,
        get_contact_chats,
        search_contacts,
        get_active_contacts,
        get_current_time,
    ]
    if os.getenv("ENABLE_SYNC", "false").lower() in ("true", "1", "yes"):
        tools.append(sync_and_report)

    agent = Agent(
        os.getenv("LLM_MODEL", "openrouter:openrouter/free"),
        deps_type=AgentDeps,
        capabilities=[Thinking(effort='high')],
        end_strategy='exhaustive',
        instructions=(
            "You are a WhatsApp assistant. Tools return JSON-formatted data — "
            "format it clearly when displaying to the user. Be concise."
        ),
        tools=tools,
    )

    history = []

    ascii_art = open('ascii-art.txt').read()
    click.secho(ascii_art, fg='green')
    click.echo("WhatsApt is ready! Type /exit or ctrl+c to quit.\n")

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
                                click.secho(delta, fg='yellow')
                            else:
                                click.secho(delta, fg='bright_white')
                            last_outputs[key] = part.content
                    history = result.all_messages()
                    click.echo()
            except Exception:
                logger.exception("Model request failed")
                click.secho("\nModel request failed. Try again or switch models.", fg='red')
    except KeyboardInterrupt:
        pass
    finally:
        click.echo("\nBye!")


if __name__ == "__main__":
    cli()
