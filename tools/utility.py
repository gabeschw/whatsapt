import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_current_time() -> str:
    """Get the current date and time.

    Use this for any time-related queries — current date, time, day of
    week, timezone context, or to determine "now" for temporal reasoning.

    Returns:
        JSON object with iso (ISO-8601 timestamp), local (human-readable
        local time), unix (Unix timestamp), weekday, and timezone.
    """
    now = datetime.now(timezone.utc).astimezone()
    result = {
        "iso": now.isoformat(),
        "local": now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z"),
        "unix": int(now.timestamp()),
        "weekday": now.strftime("%A"),
        "timezone": now.strftime("%Z"),
    }
    logger.info("Tool: get_current_time → %s", result["iso"])
    return json.dumps(result, ensure_ascii=False)
