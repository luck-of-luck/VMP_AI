"""Microsoft Teams integration — post notifications to an incoming webhook.

The webhook URL is the secret and is read from ``TEAMS_WEBHOOK_URL``.
"""

import logging
import os

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry

logger = logging.getLogger(__name__)

TEAMS_WEBHOOK_ENV = "TEAMS_WEBHOOK_URL"


async def notify_teams(text: str, title: str = "SAST Security Notification") -> dict:
    """Post a message to the configured Microsoft Teams incoming webhook.

    Args:
        text: The message body (Markdown supported by Teams).
        title: Card title.

    Returns:
        A small status dict.

    Raises:
        IntegrationError: If the webhook URL is unset or Teams returns an error.
    """
    webhook = os.environ.get(TEAMS_WEBHOOK_ENV, "").strip()
    if not webhook:
        raise IntegrationError(
            f"Microsoft Teams is not configured. Set the {TEAMS_WEBHOOK_ENV} "
            "environment variable to an incoming webhook URL."
        )

    # Legacy MessageCard format — widely supported by Teams incoming webhooks.
    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": title,
        "title": title,
        "text": text,
    }

    logger.info("Sending Microsoft Teams notification")
    resp = await post_with_retry(webhook, service="Microsoft Teams", json=card)
    return {"status_code": resp.status_code}
