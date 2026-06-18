# Decisions

## Tool return values are `str` (JSON)
Pydantic AI hangs when tools return non-string types (e.g. `list[Message]`). All tools serialize to JSON and return `str`.

## `Message(**row)` not `model_validate`
`sqlite3.Row` objects don't pass Pydantic's type check for `model_validate`.
Construct with `Message(**row)` instead.

## `search_contacts` simplified
Only searches `chats` table in messages.db. Original mcp-server version also
searched whatsmeow contacts, but that's omitted here.

## `run_stream()` + `stream_text()` pattern (with known limitation)

`main.py` uses `agent.run_stream()` with `event_stream_handler` for tool call
observation and `run.stream_text(delta=True)` for text output. This is the official
Pydantic AI pattern from the docs.

**Known limitation:** `run_stream()` stops at the first output matching the schema
(defaults to `str`, which matches any text). If the model returns text alongside
a tool call in a single response, `run_stream()` takes the text as the final
result — the tool executes (thanks to `end_strategy='exhaustive'`) but the model
never gets a follow-up request to produce a summary based on tool results. The
instruction "Call tools first, then format results for the user" mitigates this
but is unreliable (the model can ignore it).

**Future improvement options:**

1. `agent.run()` + `result.output` — simplest, absolutely reliable multi-turn,
   but no streaming (user waits for full response).

2. `run_stream_events()` — uses `run()` internally for proper multi-turn,
   streams all events through an `async for` loop, ends with an
   `AgentRunResultEvent` containing the final result. Needs a small text
   accumulator (track per-part, print on `PartEndEvent`).

## `get_chats` JOIN keeps simple form
`LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp`
is kept as-is despite a theoretical risk of duplicate rows when two messages share the same timestamp in the same chat. The edge case is too rare to justify the complexity of a `ROW_NUMBER()` subquery.