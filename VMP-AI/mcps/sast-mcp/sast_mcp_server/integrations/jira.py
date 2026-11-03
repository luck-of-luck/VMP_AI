"""Jira integration — open issues for security findings.

Targets Jira Cloud's REST API v3. Configuration is read from the environment:

- ``JIRA_URL``: Base URL, e.g. ``https://your-org.atlassian.net``.
- ``JIRA_EMAIL``: Account email for basic auth.
- ``JIRA_API_TOKEN``: API token paired with the email (basic auth).
"""

import base64
import logging
import os

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry, response_json

logger = logging.getLogger(__name__)

JIRA_URL_ENV = "JIRA_URL"
JIRA_EMAIL_ENV = "JIRA_EMAIL"
JIRA_TOKEN_ENV = "JIRA_API_TOKEN"


def _adf_document(text: str) -> dict:
    """Wrap plain text in a minimal Atlassian Document Format body."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def create_jira_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Bug",
) -> dict:
    """Create a Jira issue for a security finding.

    Args:
        project_key: The Jira project key (e.g. ``SEC``).
        summary: Issue summary/title.
        description: Issue description (plain text; wrapped into ADF).
        issue_type: Jira issue type name (default ``Bug``).

    Returns:
        The parsed JSON response from Jira (contains the new issue ``key``).

    Raises:
        IntegrationError: If credentials are missing or Jira returns an error.
    """
    base_url = os.environ.get(JIRA_URL_ENV, "").strip()
    email = os.environ.get(JIRA_EMAIL_ENV, "").strip()
    token = os.environ.get(JIRA_TOKEN_ENV, "").strip()

    if not base_url or not email or not token:
        raise IntegrationError(
            "Jira is not configured. Set the "
            f"{JIRA_URL_ENV}, {JIRA_EMAIL_ENV} and {JIRA_TOKEN_ENV} "
            "environment variables."
        )

    auth = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }
    endpoint = f"{base_url.rstrip('/')}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": _adf_document(description),
            "issuetype": {"name": issue_type},
        }
    }

    logger.info("Creating Jira issue in project %s", project_key)
    resp = await post_with_retry(
        endpoint, service="Jira", headers=headers, json=payload
    )
    return response_json(resp)
