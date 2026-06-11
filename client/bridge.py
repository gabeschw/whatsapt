import logging
import os
import subprocess
import threading
from datetime import datetime

from client import db

logger = logging.getLogger(__name__)

_WHATSAPP_BRIDGE_BINARY = os.getenv(
    "WHATSAPP_BRIDGE_BINARY",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "whatsapp-bridge",
        "whatsapp-bridge",
        "whatsapp-client",
    ),
)

_LAST_SYNC_FILE: str | None = None


def _last_sync_path() -> str:
    global _LAST_SYNC_FILE
    if _LAST_SYNC_FILE is None:
        db_path = db.MESSAGES_DB_PATH
        _LAST_SYNC_FILE = os.path.join(os.path.dirname(os.path.abspath(db_path)), ".last_sync")
    return _LAST_SYNC_FILE


def _read_last_sync() -> str | None:
    try:
        with open(_last_sync_path()) as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def _write_last_sync(timestamp: str) -> None:
    os.makedirs(os.path.dirname(_last_sync_path()), exist_ok=True)
    with open(_last_sync_path(), "w") as f:
        f.write(timestamp)


def sync(
    bridge_binary: str | None = None,
    idle_timeout: int = 15,
    max_duration: int = 300,
) -> dict:
    """Run the WhatsApp bridge in batch mode and return new messages.

    Connects to WhatsApp, collects new messages until idle, then queries
    the database for messages inserted since the last sync.

    Args:
        bridge_binary: Path to the whatsapp-client binary. Defaults to
            the whatsapp-bridge store directory.
        idle_timeout: Seconds of inactivity before batch sync completes (default 15).
        max_duration: Absolute max seconds for batch sync (default 300).

    Returns:
        Dictionary with success, total_new_messages (all inserted),
        fresh_message_count (truly new), historic_message_count (backfill),
        chats (grouped fresh messages), messages (fresh), historic_messages
        (backfill), bridge_output, and bridge_return_code.
    """
    binary = os.path.abspath(bridge_binary or _WHATSAPP_BRIDGE_BINARY)
    logger.info("Starting sync using %s", binary)
    if not os.path.isfile(binary):
        logger.warning("Bridge binary not found: %s", binary)
        return {
            "success": False,
            "error": f"Bridge binary not found: {binary}",
            "messages": [],
        }

    cwd = os.path.dirname(binary)
    cmd = [
        binary,
        "--batch",
        f"--batch-idle-timeout={idle_timeout}",
        f"--batch-max-duration={max_duration}",
    ]
    logger.info("Running: %s", " ".join(cmd))

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    timed_out = False

    def _read_stream(stream, log, lines):
        for raw in iter(stream.readline, ""):
            line = raw.rstrip("\n")
            if not line:
                continue
            log("  [bridge] %s", line)
            lines.append(line)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        logger.warning("Bridge binary not executable: %s", binary)
        return {
            "success": False,
            "error": f"Bridge binary not executable: {binary}",
            "messages": [],
        }

    t1 = threading.Thread(target=_read_stream, args=(proc.stdout, logger.info, stdout_lines), daemon=True)
    t2 = threading.Thread(target=_read_stream, args=(proc.stderr, logger.warning, stderr_lines), daemon=True)
    t1.start()
    t2.start()

    try:
        proc.wait(timeout=max_duration + 30)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        logger.warning("Bridge timed out after %ds", max_duration + 30)

    t1.join(timeout=5)
    t2.join(timeout=5)

    if timed_out:
        return {
            "success": False,
            "error": f"Bridge timed out after {max_duration + 30}s",
            "messages": [],
        }

    if proc.returncode != 0:
        logger.warning("Bridge exited with code %d", proc.returncode)
        return {
            "success": False,
            "error": f"Bridge exited with code {proc.returncode}: {stderr_lines[-1] if stderr_lines else 'unknown'}",
            "messages": [],
        }

    last_sync = _read_last_sync()

    pre_conn = db.connect()
    try:
        pre_sync = db.get_messages(pre_conn, limit=1, sort_by="newest")
        pre_sync_cutoff = pre_sync[0].timestamp if pre_sync else None
    finally:
        pre_conn.close()

    conn = db.connect()
    try:
        messages = db.get_messages(
            conn,
            after_inserted_at=last_sync,
            sort_by="oldest",
            limit=500,
        )
    finally:
        conn.close()

    _write_last_sync(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    fresh = []
    historic = []
    for msg in messages:
        if pre_sync_cutoff is not None and msg.timestamp <= pre_sync_cutoff:
            historic.append(msg)
        else:
            fresh.append(msg)

    grouped: dict[str, dict] = {}
    for msg in fresh:
        chat_key = msg.chat_jid or "unknown"
        if chat_key not in grouped:
            grouped[chat_key] = {
                "chat_jid": chat_key,
                "chat_name": msg.chat_name,
                "message_count": 0,
                "messages": [],
            }
        grouped[chat_key]["message_count"] += 1
        grouped[chat_key]["messages"].append(msg.model_dump(mode="json"))

    logger.info(
        "Sync complete: %d new (%d fresh, %d historic) across %d chats",
        len(messages), len(fresh), len(historic), len(grouped),
    )
    return {
        "success": True,
        "total_new_messages": len(messages),
        "fresh_message_count": len(fresh),
        "historic_message_count": len(historic),
        "chats": sorted(grouped.values(), key=lambda c: c["message_count"], reverse=True),
        "messages": [msg.model_dump(mode="json") for msg in fresh],
        "historic_messages": [msg.model_dump(mode="json") for msg in historic],
        "bridge_output": "\n".join(stdout_lines[-20:]),
        "bridge_return_code": proc.returncode,
    }
