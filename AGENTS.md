# whatsapt — Agent instructions

## Interaction

- Challenge me on a regular basis. Don't just agree — push back when something is unclear, suboptimal, or inconsistent. If I'm about to make a mistake, tell me.

## Toolchain

- **Package manager**: `uv` (not pip/poetry). Run everything via `uv run`.
- **Python version**: 3.12 (`.python-version`).
- **Lint**: `uv run ruff check .` — config in `pyproject.toml` (target py312, 100 cols).
- **Test**: `uv run pytest -v` — 54 tests in `tests/`.
- **Typecheck**: not configured.

## Common commands

| Action | Command |
|--------|---------|
| Lint | `uv run ruff check .` |
| Test | `uv run pytest -v` |
| Run | `uv run python main.py` |
| Add dep | `uv add <pkg>` |
| Add dev dep | `uv add --dev <pkg>` |

`uv lock` regenerates lockfile automatically on `uv add`.

## Architecture

```
main.py              Entrypoint — interactive chat loop, registers 7 tools
client/db.py         SQLite query layer (7 public functions: get_messages, get_chats, etc.)
client/bridge.py     Runs whatsapp-client --batch as subprocess, returns new messages
client/models.py     Pydantic models: Message, Chat, Contact, MessageContext
tools/deps.py        AgentDeps dataclass (holds conn: sqlite3.Connection)
tools/queries.py     All 7 Pydantic AI tools (search_messages, get_message_context, etc.)
tests/               54 tests using in-memory SQLite fixtures
```

## Key conventions

- **Tool return type**: All tools return `str` (JSON). Pydantic AI hangs on non-string return types.
- **Tool signature**: `fn(ctx: RunContext[AgentDeps], ...) -> str`. Log the DB function call and result count.
- **DB models**: Construct with `Message(**row)`, not `model_validate` — `sqlite3.Row` fails Pydantic's type check.
- **No section separator comments** (`# ----`, `# ====`) in code.
- **Logging**: Visibility lives in `tools/queries.py`, not in `client/db.py`.

## Env vars

Documented in `.env.example`. Key vars:
- `MESSAGES_DB_PATH` — path to the bridge's messages.db
- `WHATSAPP_DB_PATH` — path to whatsapp.db (LID/contact lookups)
- `WHATSAPP_BRIDGE_BINARY` — path to `whatsapp-client` binary
- `LLM_MODEL` — OpenRouter model ID (e.g. `openrouter:openrouter/free`)
- `OPENROUTER_API_KEY`

## DB details

- `MESSAGES_DB_PATH` is the bridge's `messages.db`. `WHATSAPP_DB_PATH` is the whatsmeow store (`whatsapp.db`).
- `get_sender_name` resolves phone/LID aliases via `_sender_aliases()` — expands bare phone, `@s.whatsapp.net`, `@lid`, and LID mappings.
- `Message.timestamp` is a `datetime` object. `sqlite3.register_adapter(datetime.datetime, lambda val: val.isoformat())` is registered at module load for Python 3.12 compatibility.
- `after_inserted_at` uses `inserted_at` column timestamps (ISO-8601 strings).
- `check_same_thread=False` on the connection — the agent runs tools in a thread pool.

## Bridge

- Bridges are Go binaries at `whatsapp-bridge/whatsapp-bridge/`.
- Sync runs `whatsapp-client --batch --batch-idle-timeout=15 --batch-max-duration=300`.
- `.last_sync` file in the store directory tracks sync cursor.
- Bridge output streams to logger in real-time with `[bridge]` prefix.
- Sync splits results into `messages` (fresh — timestamps newer than pre-sync newest) and `historic_messages` (backfill — older timestamps the bridge pulled).

## Gotchas

- `.gitignore` excludes `PLAN.md`, `.env`, and `temp/`.
- `DECISIONS.md` is user-maintained — never edit without explicit request.
- `get_contacts` searches only the `chats` table (not whatsmeow contacts).
- `chats.name` may contain phone numbers; `get_sender_name` filters those with `.isdigit()` check.
- The bridge's store path is relative to its working directory (`os.MkdirAll("store", 0755)` in Go).
