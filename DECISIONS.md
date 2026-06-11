# Decisions

## Tool return values are `str` (JSON)
Pydantic AI hangs when tools return non-string types (e.g. `list[Message]`). All tools serialize to JSON and return `str`.

## `Message(**row)` not `model_validate`
`sqlite3.Row` objects don't pass Pydantic's type check for `model_validate`.
Construct with `Message(**row)` instead.

## `search_contacts` simplified
Only searches `chats` table in messages.db. Original mcp-server version also
searched whatsmeow contacts, but that's omitted here.

## `get_chats` JOIN keeps simple form
`LEFT JOIN messages m ON c.jid = m.chat_jid AND c.last_message_time = m.timestamp`
is kept as-is despite a theoretical risk of duplicate rows when two messages share the same timestamp in the same chat. The edge case is too rare to justify the complexity of a `ROW_NUMBER()` subquery.