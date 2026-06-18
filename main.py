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
    TextPartDelta,
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


async def handle_event(event: AgentStreamEvent) -> None:
    if isinstance(event, PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, TextPartDelta):
            logger.debug("text_delta index=%d len=%d", event.index, len(delta.content_delta))
        elif isinstance(delta, ThinkingPartDelta):
            logger.debug("thinking_delta index=%d len=%d", event.index, len(delta.content_delta))
    elif isinstance(event, FunctionToolCallEvent):
        logger.debug(
            "tool_call name=%s args=%s",
            event.part.tool_name,
            getattr(event.part, 'args', None),
        )
        click.secho(f"[tool: {event.part.tool_name}]", fg='cyan')
    elif isinstance(event, FunctionToolResultEvent):
        logger.debug("tool_result name=%s", event.part.tool_name if event.part else 'unknown')
        click.secho('[done]', fg='cyan')


async def event_stream_handler(
    ctx: RunContext[AgentDeps],
    events: AsyncIterable[AgentStreamEvent],
) -> None:
    async for event in events:
        await handle_event(event)


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
                async with agent.run_stream(
                    prompt,
                    deps=deps,
                    message_history=history,
                    retries=2,
                    event_stream_handler=event_stream_handler,
                ) as run:
                    async for delta in run.stream_text(delta=True):
                        click.secho(delta, fg='bright_white', nl=False)
                    history = run.all_messages()
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
