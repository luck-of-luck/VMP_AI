"""Slack integration — post notifications to an incoming webhook.

The webhook URL is itself the secret and is read from ``SLACK_WEBHOOK_URL``;
no token is accepted as a tool argument.
"""

import logging
import os

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_ENV = "SLACK_WEBHOOK_URL"


async def notify_slack(text: str) -> dict:
    """Post a message to the configured Slack incoming webhook.

    Args:
        text: The message text (Slack mrkdwn supported).

    Returns:
        A small status dict.

    Raises:
        IntegrationError: If the webhook URL is unset or Slack returns an error.
    """
    webhook = os.environ.get(SLACK_WEBHOOK_ENV, "").strip()
    if not webhook:
        raise IntegrationError(
            f"Slack is not configured. Set the {SLACK_WEBHOOK_ENV} "
            "environment variable to an incoming webhook URL."
        )

    logger.info("Sending Slack notification")
    resp = await post_with_retry(webhook, service="Slack", json={"text": text})
    return {"status_code": resp.status_code}
