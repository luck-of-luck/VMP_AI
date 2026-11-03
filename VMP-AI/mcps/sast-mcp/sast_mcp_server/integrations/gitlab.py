"""GitLab integration — post security summaries on merge requests.

Configuration is read from the environment:

- ``GITLAB_TOKEN``: A personal/project access token with ``api`` scope
  (sent as the ``PRIVATE-TOKEN`` header).
- ``GITLAB_URL``: Base URL of the GitLab instance (defaults to
  ``https://gitlab.com``; override for self-managed instances).
"""

import logging
import os
from urllib.parse import quote

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry, response_json

logger = logging.getLogger(__name__)

GITLAB_TOKEN_ENV = "GITLAB_TOKEN"
GITLAB_URL_ENV = "GITLAB_URL"
DEFAULT_GITLAB_URL = "https://gitlab.com"


async def comment_on_merge_request(
    project_id: str,
    merge_request_iid: int,
    body: str,
) -> dict:
    """Post a note (comment) on a GitLab merge request.

    Args:
        project_id: Numeric project ID or URL-encoded ``group/project`` path.
        merge_request_iid: The merge request IID (project-scoped number).
        body: Markdown note body.

    Returns:
        The parsed JSON response from GitLab (contains the note ``id``).

    Raises:
        IntegrationError: If the token is missing or GitLab returns an error.
    """
    token = os.environ.get(GITLAB_TOKEN_ENV, "").strip()
    if not token:
        raise IntegrationError(
            f"GitLab is not configured. Set the {GITLAB_TOKEN_ENV} "
            "environment variable (needs 'api' scope)."
        )

    base_url = os.environ.get(GITLAB_URL_ENV, "").strip() or DEFAULT_GITLAB_URL
    project = quote(str(project_id), safe="")
    endpoint = (
        f"{base_url.rstrip('/')}/api/v4/projects/{project}"
        f"/merge_requests/{merge_request_iid}/notes"
    )
    headers = {"PRIVATE-TOKEN": token}

    logger.info("Commenting on GitLab MR %s!%d", project_id, merge_request_iid)
    resp = await post_with_retry(
        endpoint, service="GitLab", headers=headers, json={"body": body}
    )
    return response_json(resp)
