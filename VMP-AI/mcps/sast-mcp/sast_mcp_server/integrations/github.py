"""GitHub Code Scanning integration — upload SARIF to a repository.

Posts a SARIF report to GitHub's
``POST /repos/{owner}/{repo}/code-scanning/sarifs`` REST endpoint. The API
requires the SARIF payload to be gzip-compressed and base64-encoded.

Configuration is read from the environment:

- ``GITHUB_TOKEN``: A token with ``security_events: write`` scope
  (used as ``Authorization: Bearer ...``).
"""

import base64
import gzip
import logging
import os

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry, response_json

logger = logging.getLogger(__name__)

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


def _github_token() -> str:
    """Return the configured GitHub token or raise if unset."""
    token = os.environ.get(GITHUB_TOKEN_ENV, "").strip()
    if not token:
        raise IntegrationError(
            f"GitHub is not configured. Set the {GITHUB_TOKEN_ENV} "
            "environment variable (needs security_events: write scope)."
        )
    return token


def _github_headers(token: str) -> dict:
    """Standard GitHub REST API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def _validate_repo(repo: str) -> None:
    """Ensure ``repo`` is in ``owner/name`` form."""
    if "/" not in repo or repo.count("/") != 1:
        raise IntegrationError(
            f"Invalid repo '{repo}'. Expected 'owner/name' format."
        )


async def upload_to_github(
    sarif_path: str,
    repo: str,
    commit_sha: str,
    ref: str,
    api_base: str = GITHUB_API_BASE,
) -> dict:
    """Upload a SARIF report to GitHub Code Scanning.

    Args:
        sarif_path: Path to a SARIF file produced by ``export_sarif``.
        repo: Repository in ``owner/name`` form.
        commit_sha: The full SHA of the commit the results apply to.
        ref: The fully qualified ref (e.g. ``refs/heads/main``).
        api_base: GitHub API base URL (override for GitHub Enterprise).

    Returns:
        The parsed JSON response from GitHub (contains the analysis ``id``
        and a ``url`` to poll processing status).

    Raises:
        IntegrationError: If the token is missing, ``repo`` is malformed, the
            file is unreadable, or GitHub returns a non-success status.
    """
    token = _github_token()
    _validate_repo(repo)

    try:
        with open(sarif_path, "rb") as f:
            sarif_bytes = f.read()
    except OSError as err:
        raise IntegrationError(f"Could not read SARIF file '{sarif_path}': {err}") from err

    encoded = base64.b64encode(gzip.compress(sarif_bytes)).decode("ascii")
    endpoint = f"{api_base.rstrip('/')}/repos/{repo}/code-scanning/sarifs"
    body = {"commit_sha": commit_sha, "ref": ref, "sarif": encoded}

    logger.info("Uploading SARIF to GitHub Code Scanning for %s", repo)
    resp = await post_with_retry(
        endpoint, service="GitHub", headers=_github_headers(token), json=body
    )
    return response_json(resp)


async def comment_on_pull_request(
    repo: str,
    pr_number: int,
    body: str,
    api_base: str = GITHUB_API_BASE,
) -> dict:
    """Post a top-level comment on a GitHub pull request.

    Uses the issues comment endpoint (a PR is an issue), which posts a general
    PR comment rather than an inline diff comment — the right surface for a
    security summary.

    Args:
        repo: Repository in ``owner/name`` form.
        pr_number: The pull request number.
        body: Markdown comment body.
        api_base: GitHub API base URL (override for GitHub Enterprise).

    Returns:
        The parsed JSON response from GitHub (contains the comment ``id``/``html_url``).

    Raises:
        IntegrationError: If the token is missing, ``repo`` is malformed, or
            GitHub returns a non-success status.
    """
    token = _github_token()
    _validate_repo(repo)

    endpoint = f"{api_base.rstrip('/')}/repos/{repo}/issues/{pr_number}/comments"
    logger.info("Commenting on GitHub PR %s#%d", repo, pr_number)
    resp = await post_with_retry(
        endpoint, service="GitHub", headers=_github_headers(token), json={"body": body}
    )
    return response_json(resp)
