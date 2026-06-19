import asyncio
import logging
import os
from collections.abc import AsyncIterable

import rich_click as click
import click_log

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
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

async def event_stream_handler(
    ctx: RunContext[AgentDeps],
    events: AsyncIterable[AgentStreamEvent],
) -> None:

    async for event in events:
        # Catch the initial tokens the parser swallowed
        if isinstance(event, PartStartEvent):
            if isinstance(event.part, TextPart) and event.part.content:
                content = event.part.content.replace('</think>', '')
                click.secho(content, nl=False)
            elif isinstance(event.part, ThinkingPart) and event.part.content:
                click.secho(event.part.content, dim=True, nl=False)

        # Stream the rest of the deltas as they arrive
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                click.secho(event.delta.content_delta, nl=False)
            elif isinstance(event.delta, ThinkingPartDelta):
                click.secho(event.delta.content_delta, dim=True, nl=False)
            
        # Add newlines when blocks finish
        elif isinstance(event, PartEndEvent):
            click.echo() 
            
        # Notify and log tool usage
        elif isinstance(event, FunctionToolCallEvent):
            name = event.part.tool_name
            # Notice we don't use isinstance for args because args might be a dict or a BaseModel
            logger.debug("tool_call name=%s args=%s", name, getattr(event.part, 'args', None))
            click.secho(f"\n[tool: {name}]", fg='cyan')
            
        elif isinstance(event, FunctionToolResultEvent):
            name = event.part.tool_name if event.part else 'unknown'
            logger.debug("tool_result name=%s", name)
            click.secho(f"[done: {name}]", fg='cyan')


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
            "Call tools first, then format results clearly for the user."
            "Be concise. Do not use unnecessary emojis."
        ),
        tools=tools,
    )

    history = []

    ascii_art = open('ascii-art.txt').read()
    click.secho(ascii_art, fg='green')
    click.secho(
        "WhatsApt is ready! Type /exit or ctrl+c to quit.\n",
        fg='green', bold=True
    )

    try:
        while True:
            try:
                prompt = (await asyncio.to_thread(
                    click.prompt,
                    click.style("»", fg="yellow", bold=True), 
                    prompt_suffix=" ", 
                    show_default=False,
                )).strip()
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
