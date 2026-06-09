# whatsapt — Agent instructions

## Toolchain

- **Package manager**: `uv` (not pip/poetry). Run everything via `uv run`.
- **Python**: 3.12 enforced by `.python-version`.
- **Lint**: `uv run ruff check .` — config at `ruff.toml` (py312, 100 cols).
- **Test**: `uv run pytest -v` — no tests written yet.
- **Typecheck**: not configured.

## Common commands

| Action | Command |
|--------|---------|
| Add runtime dep | `uv add <pkg>` |
| Add dev dep | `uv add --dev <pkg>` |
| Lint | `uv run ruff check .` |
| Test | `uv run pytest -v` |

`uv lock` regenerates lockfile automatically on `uv add`.

## Code & structure

- `main.py` — temporary entrypoint that calls `client/db.py`.
- `client/db.py` — three functions: `connect()`, `recent_messages()`, `print_messages()`. Uses built-in `sqlite3`. Reads `WHATSAPP_DB_PATH` env var, falls back to `./messages.db`.
- `client/` is the bridge layer. `bridge.py` (httpx) and `audio.py` (FFmpeg) planned.
- `tools/` is planned — Pydantic AI tools mirroring the MCP server's tool set.
- Env vars prefixed `WHATSAPP_`, `LLM_`. `.env` is gitignored; `.env.example` documents vars.

## Design intent

- Pydantic AI agent with typed tools
- `AgentDeps` holds bridge client + DB, initialized at CLI startup
- Tool layer in `tools/` mirrors MCP server's tool set (same params, same behavior)

## Gotchas

- `.gitignore` excludes `PLAN.md` and `.env` — don't commit either.
- No tests directory exists yet — create one when adding tests.
- No CI, no git history (zero commits).
