# Decisions

## Tool return values are `str` (JSON)
Pydantic AI hangs when tools return non-string types (e.g. `list[Message]`). All tools serialize to JSON and return `str`.

## `Message(**row)` not `model_validate`
`sqlite3.Row` objects don't pass Pydantic's type check for `model_validate`.
Construct with `Message(**row)` instead.

## `search_contacts` simplified
Only searches `chats` table in messages.db. Original mcp-server version also
searched whatsmeow contacts, but that's omitted here.

## `agent.run()` with hybrid output

`main.py` uses `agent.run()` with `event_stream_handler` for real-time
indicators and `result.output` for complete text.

The handler processes:
- `FunctionToolCallEvent` / `FunctionToolResultEvent` → prints `[tool: ...]` / `[done]` indicators
- `PartDeltaEvent` (thinking only) → accumulates thinking deltas per part index
- `PartEndEvent` (thinking only) → prints accumulated thinking in full

Text is printed from `result.output` after the run completes, avoiding
delta-accumulation issues where content gets split across part boundaries.

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