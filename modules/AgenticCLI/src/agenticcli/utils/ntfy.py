"""ntfy.sh push notification client.

HTTP client for sending and receiving push notifications via ntfy.sh.
Uses urllib.request (stdlib) - no external dependencies required.
"""

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def send_ntfy(
    topic: str,
    title: str,
    message: str,
    priority: str = "default",
    server: str = "https://ntfy.sh",
    tags: list[str] | None = None,
) -> bool:
    """Send a push notification via ntfy.

    Args:
        topic: ntfy topic name.
        title: Notification title.
        message: Notification body text.
        priority: Priority level (min, low, default, high, urgent).
        server: ntfy server URL.
        tags: Optional list of emoji tags.

    Returns:
        True on success (2xx response), False on error.
    """
    url = f"{server.rstrip('/')}/{topic}"

    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    req = Request(
        url,
        data=message.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        resp = urlopen(req, timeout=5)
        status = resp.getcode()
        resp.close()
        return 200 <= status < 300
    except HTTPError as e:
        logger.warning("ntfy HTTP error %d for topic '%s': %s", e.code, topic, e.reason)
        return False
    except URLError as e:
        logger.warning("ntfy network error for topic '%s': %s", topic, e.reason)
        return False
    except OSError as e:
        logger.warning("ntfy request failed for topic '%s': %s", topic, e)
        return False


def poll_ntfy(
    topic: str,
    since: str = "30m",
    server: str = "https://ntfy.sh",
) -> list[dict]:
    """Poll an ntfy topic for recent messages.

    Fetches messages from the ntfy JSON polling endpoint. Returns a list
    of message dicts, or an empty list on any error (non-throwing).

    Args:
        topic: ntfy topic name.
        since: Time window - relative ("30m", "1h"), unix timestamp, or message ID.
        server: ntfy server URL.

    Returns:
        List of message dicts with at minimum {id, time, message} keys.
    """
    url = f"{server.rstrip('/')}/{topic}/json?since={since}&poll=1"

    req = Request(url, method="GET")

    try:
        resp = urlopen(req, timeout=5)
        body = resp.read().decode("utf-8")
        resp.close()
    except (HTTPError, URLError, OSError) as e:
        logger.warning("ntfy poll error for topic '%s': %s", topic, e)
        return []

    messages = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            messages.append(msg)
        except json.JSONDecodeError:
            logger.warning("ntfy poll: skipping malformed JSON line")
            continue

    return messages


def parse_question_id_from_message(message: str) -> str | None:
    """Extract a question ID from an ntfy message body.

    Searches for the pattern [QID: Q-XXXXXXXX-XXXXXX-XXXX] in the message
    text. Returns the first matching question ID, or None if no match.

    Args:
        message: The ntfy message body text.

    Returns:
        Question ID string (e.g. "Q-20260208-120000-abc1") or None.
    """
    match = re.search(r'\[QID:\s*(Q-\d{8}-\d{6}-[0-9a-f]{4})\]', message)
    if match:
        return match.group(1)
    return None


def notify_new_question(
    topic: str,
    question: "Question",
    server: str = "https://ntfy.sh",
) -> bool:
    """Send a push notification for a new pending question.

    Formats the notification with severity-appropriate priority and tags.

    Args:
        topic: ntfy topic name.
        question: Question instance from the question model.
        server: ntfy server URL.

    Returns:
        True on success, False on error.
    """
    severity = getattr(question, "severity", "medium").lower()

    title = f"New Question [{severity.upper()}]"

    text = getattr(question, "text", "")
    message = text[:200] + "..." if len(text) > 200 else text

    # Append lettered options if suggested_answers present
    suggested = getattr(question, "suggested_answers", None)
    if suggested and isinstance(suggested, list) and len(suggested) > 0:
        message += "\n"
        for i, answer in enumerate(suggested[:10]):  # Max 10 options (A-J)
            letter = chr(ord('A') + i)
            message += f"\n{letter}) {answer}"

    # Append question ID footer for reply matching
    q_id = getattr(question, "id", "")
    if q_id:
        message = f"{message}\n\n[QID: {q_id}]"

    if severity == "blocking":
        priority = "urgent"
        tags = ["warning"]
    elif severity == "high":
        priority = "high"
        tags = ["question"]
    else:
        priority = "default"
        tags = ["question"]

    return send_ntfy(
        topic=topic,
        title=title,
        message=message,
        priority=priority,
        server=server,
        tags=tags,
    )
