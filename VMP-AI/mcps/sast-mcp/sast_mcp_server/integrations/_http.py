"""Shared async HTTP helper for outbound integrations.

Centralizes retry-with-exponential-backoff, timeout handling, and uniform error
translation to :class:`IntegrationError` so every integration behaves consistently.

Transient failures (network errors and 5xx / 429 responses) are retried; 4xx
responses are treated as permanent and raised immediately.
"""

import asyncio
import logging

import httpx

from sast_mcp_server.config import get_settings
from sast_mcp_server.integrations import IntegrationError

logger = logging.getLogger(__name__)

# Status codes worth retrying (server-side / rate limiting).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff: 0.5s, 1s, 2s, ... capped at 10s."""
    return float(min(0.5 * (2 ** attempt), 10.0))


async def post_with_retry(
    url: str,
    *,
    service: str,
    headers: dict | None = None,
    json: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
    timeout: float | None = None,
    retries: int | None = None,
) -> httpx.Response:
    """POST with retries/backoff, returning the response on a 2xx/3xx status.

    Args:
        url: Target endpoint.
        service: Human-readable service name used in error messages (e.g. "GitHub").
        headers/json/data/files: Forwarded to ``httpx.AsyncClient.post``.
        timeout: Per-request timeout; defaults to the configured HTTP timeout.
        retries: Max retry attempts; defaults to the configured retry count.

    Returns:
        The successful ``httpx.Response``.

    Raises:
        IntegrationError: On a non-retryable 4xx, exhausted retries, or transport error.
    """
    settings = get_settings()
    timeout = settings.http_timeout if timeout is None else timeout
    retries = settings.http_retries if retries is None else retries

    last_error: str = "unknown error"
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(retries + 1):
            try:
                resp = await client.post(
                    url, headers=headers, json=json, data=data, files=files
                )
            except httpx.HTTPError as err:
                last_error = f"{service} request failed: {err}"
                logger.warning(
                    "%s POST %s transport error (attempt %d/%d): %s",
                    service, url, attempt + 1, retries + 1, err,
                )
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                    last_error = f"{service} returned {resp.status_code}"
                    logger.warning(
                        "%s returned %d (attempt %d/%d); retrying",
                        service, resp.status_code, attempt + 1, retries + 1,
                    )
                else:
                    # Permanent failure — surface the body for diagnosis.
                    raise IntegrationError(
                        f"{service} returned {resp.status_code}: {resp.text[:500]}"
                    )

            if attempt < retries:
                await asyncio.sleep(_backoff_seconds(attempt))

    raise IntegrationError(f"{service} request failed after {retries + 1} attempts: {last_error}")


def response_json(resp: httpx.Response) -> dict:
    """Parse a response body as a JSON object, tolerating non-dict/non-JSON bodies."""
    try:
        data = resp.json()
    except ValueError:
        return {"status_code": resp.status_code, "text": resp.text}
    return data if isinstance(data, dict) else {"response": data}
