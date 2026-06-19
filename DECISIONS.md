# Decisions

## Tool return values are `str` (JSON)
Pydantic AI hangs when tools return non-string types (e.g. `list[Message]`). All tools serialize to JSON and return `str`.

## `Message(**row)` not `model_validate`
`sqlite3.Row` objects don't pass Pydantic's type check for `model_validate`.
Construct with `Message(**row)` instead.

## `search_contacts` simplified
Only searches `chats` table in messages.db. Original mcp-server version also
searched whatsmeow contacts, but that's omitted here.

## `agent.run()` with `event_stream_handler`

`main.py` uses `agent.run()` with `event_stream_handler` for real-time
streaming of all output — text, thinking, and tool indicators.

The handler processes five event types:
- `PartStartEvent` — catches initial tokens the stream parser swallowed.
  Prints `TextPart` content directly, `ThinkingPart` content dimmed.
- `PartDeltaEvent` — streams deltas as they arrive.
  `TextPartDelta` content printed directly, `ThinkingPartDelta` dimmed.
- `PartEndEvent` — prints a newline when a text/thinking block finishes.
- `FunctionToolCallEvent` / `FunctionToolResultEvent` — prints
  `[tool: name]` / `[done: name]` indicators in cyan.

After the run, `result.all_messages()` captures the full conversation
history for the next prompt turn.

`run_stream()` was rejected because it stops at the first output matching the
`schema` (defaults to `str`, which matches any text). If the model returns text
alongside a tool call, `run_stream()` takes the text as the final result — the
tool executes (thanks to `end_strategy='exhaustive'`) but the model never gets
a follow-up request to produce a summary.

`run_stream_events()` wasn't chosen because it doesn't return a `result` object
— `result.all_messages()` is needed for conversation history across prompts.

## `get_chats` JOIN keeps simple form
`LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp`
is kept as-is despite a theoretical risk of duplicate rows when two messages share the same timestamp in the same chat. The edge case is too rare to justify the complexity of a `ROW_NUMBER()` subquery.