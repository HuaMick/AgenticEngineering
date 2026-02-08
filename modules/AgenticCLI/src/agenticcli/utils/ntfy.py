"""ntfy.sh push notification client.

HTTP client for sending push notifications via ntfy.sh.
Uses urllib.request (stdlib) - no external dependencies required.
"""

import logging
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
