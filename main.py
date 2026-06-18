import asyncio
import logging
import os
from collections.abc import AsyncIterable

import click
import click_log

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    ThinkingPartDelta,
)
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

# Pin HTTP transport loggers to WARNING so -vv doesn't spam with request tracing
for other_logger in ("openai", "httpx", "httpcore"):
    logging.getLogger(other_logger).setLevel(logging.WARNING)


async def handle_event(
    event: AgentStreamEvent,
    text_buffers: dict[int, str] | None = None,
) -> None:
    if isinstance(event, PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, ThinkingPartDelta) and text_buffers is not None:
            text_buffers[event.index] = text_buffers.get(event.index, '') + delta.content_delta
    elif isinstance(event, PartEndEvent):
        part = event.part
        kind = part.part_kind if part else 'unknown'
        if kind == 'thinking' and text_buffers is not None:
            content = text_buffers.pop(event.index, '')
            if content:
                click.secho(content, fg='yellow')
    elif isinstance(event, FunctionToolCallEvent):
        name = event.part.tool_name
        logger.debug("tool_call name=%s args=%s", name, getattr(event.part, 'args', None))
        click.secho(f"[tool: {name}]", fg='cyan')
    elif isinstance(event, FunctionToolResultEvent):
        name = event.part.tool_name if event.part else 'unknown'
        logger.debug("tool_result name=%s", name)
        click.secho('[done]', fg='cyan')


async def event_stream_handler(
    ctx: RunContext[AgentDeps],
    events: AsyncIterable[AgentStreamEvent],
) -> None:
    buffers: dict[int, str] = {}
    async for event in events:
        await handle_event(event, buffers)


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
            "You are a WhatsApp assistant. Tools return JSON-formatted data. "
            "Call tools first, then format results clearly for the user. Be concise."
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
                result = await agent.run(
                    prompt,
                    deps=deps,
                    message_history=history,
                    retries=2,
                    event_stream_handler=event_stream_handler,
                )
                history = result.all_messages()
                if result.output:
                    click.secho(str(result.output), fg='bright_white')
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
