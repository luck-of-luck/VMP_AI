"""DefectDojo integration — import SARIF results into an engagement.

Uploads a SARIF report to DefectDojo's ``/api/v2/import-scan/`` endpoint.
Configuration is read from the environment:

- ``DEFECTDOJO_URL``: Base URL of the DefectDojo instance
  (e.g. ``https://defectdojo.example.com``).
- ``DEFECTDOJO_API_KEY``: API v2 token used for ``Authorization: Token ...``.
"""

import logging
import os

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.integrations._http import post_with_retry, response_json

logger = logging.getLogger(__name__)

DEFECTDOJO_URL_ENV = "DEFECTDOJO_URL"
DEFECTDOJO_API_KEY_ENV = "DEFECTDOJO_API_KEY"

# DefectDojo natively understands the SARIF scan type.
DEFAULT_SCAN_TYPE = "SARIF"


async def upload_to_defectdojo(
    sarif_path: str,
    engagement_id: int,
    scan_type: str = DEFAULT_SCAN_TYPE,
    active: bool = True,
    verified: bool = False,
) -> dict:
    """Import a SARIF report into a DefectDojo engagement.

    Args:
        sarif_path: Path to a SARIF file produced by ``export_sarif``.
        engagement_id: Numeric ID of the target DefectDojo engagement.
        scan_type: DefectDojo scan type. Defaults to ``"SARIF"``.
        active: Whether imported findings are marked active.
        verified: Whether imported findings are marked verified.

    Returns:
        The parsed JSON response from DefectDojo.

    Raises:
        IntegrationError: If credentials are missing, the file is unreadable,
            or DefectDojo returns a non-success status.
    """
    base_url = os.environ.get(DEFECTDOJO_URL_ENV, "").strip()
    api_key = os.environ.get(DEFECTDOJO_API_KEY_ENV, "").strip()

    if not base_url or not api_key:
        raise IntegrationError(
            "DefectDojo is not configured. Set the "
            f"{DEFECTDOJO_URL_ENV} and {DEFECTDOJO_API_KEY_ENV} "
            "environment variables."
        )

    try:
        with open(sarif_path, "rb") as f:
            sarif_bytes = f.read()
    except OSError as err:
        raise IntegrationError(f"Could not read SARIF file '{sarif_path}': {err}") from err

    endpoint = f"{base_url.rstrip('/')}/api/v2/import-scan/"
    headers = {"Authorization": f"Token {api_key}"}
    data = {
        "engagement": str(engagement_id),
        "scan_type": scan_type,
        "active": str(active).lower(),
        "verified": str(verified).lower(),
    }
    files = {
        "file": (os.path.basename(sarif_path) or "results.sarif", sarif_bytes, "application/json"),
    }

    logger.info("Uploading SARIF to DefectDojo engagement %s", engagement_id)
    resp = await post_with_retry(
        endpoint, service="DefectDojo", headers=headers, data=data, files=files
    )
    return response_json(resp)
