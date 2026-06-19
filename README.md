# whatsapt

WhatsApp AI assistant to focus just on what is important in your WhatsApp messages.

Requires [whatsapp-bridge](https://github.com/gabeschw/whatsapp-bridge) to populate the SQLite database.

## Quick start

```bash
cp .env.example .env   # fill in your keys and paths
uv run --env-file=.env main.py
```

## Planned features

- Better integration with whatsapp-bridge to keep the database current without manual sync.
- Automated summaries: scheduled and configurable per-chat rules for what to summarize, what to ignore, and level of detail. 
- RAG-based research: ask questions against your full message history with retrieved context.
- Unanswered message detection: find messages you never replied to within a time window.
- Contact/group insights: identify who you talk to most, time patterns, which groups are inactive or unimportant
