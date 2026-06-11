# whatsapt — Agent instructions

## Interaction

- Challenge me on a regular basis. Don't just agree — push back when something is
  unclear, suboptimal, or inconsistent. If I'm about to make a mistake, tell me.

## Toolchain

- **Package manager**: `uv` (not pip/poetry). Run everything via `uv run`.
- **Python**: 3.12 enforced by `.python-version`.
- **Lint**: `uv run ruff check .` — config at `ruff.toml` (py312, 100 cols).
- **Test**: `uv run pytest -v` 
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

- `main.py` — entrypoint: creates `AgentDeps`, sets up the Pydantic AI agent, registers tools, runs the agent loop.
- `client/db.py` — `connect()`, `recent_messages()`. Uses built-in `sqlite3`. Reads `MESSAGES_DB_PATH` env var.
- `client/models.py` — `Message` Pydantic model.
- `client/` is the bridge layer. `bridge.py` (httpx) and `audio.py` (FFmpeg) planned.
- `tools/deps.py` — `AgentDeps` dataclass (holds DB connection).
- `tools/` — Pydantic AI tools mirroring the MCP server's tool set. Add new tools as modules here and register them in `main.py`.
- Env vars prefixed `WHATSAPP_`, `LLM_`, `OPENROUTER_`. `.env` is gitignored; `.env.example` documents vars.

## Code style

- **No section separator comments** — don't use banner comments like
  `# ----` or `# ====` to group code. Functions speak for themselves.

## Design intent

- Pydantic AI agent with typed tools
- `AgentDeps` holds bridge client + DB, initialized at CLI startup
- Tool layer in `tools/` mirrors MCP server's tool set (same params, same behavior)

## Gotchas

- `.gitignore` excludes `PLAN.md` and `.env` — don't commit either.
- `DECISIONS.md` is maintained by the user only — never edit it without explicit request.
- No tests directory exists yet — create one when adding tests.
- No CI, no git history (zero commits).
