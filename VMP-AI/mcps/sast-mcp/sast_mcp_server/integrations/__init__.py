"""Third-party dashboard integrations for SAST MCP Server.

Each integration pushes standardized SARIF exports to an external security
platform. Credentials are read exclusively from environment variables so that
secrets never appear in tool arguments or agent transcripts.
"""


class IntegrationError(Exception):
    """Raised when an outbound integration cannot complete.

    Covers missing configuration (e.g. unset credentials), unreadable input
    files, and non-success HTTP responses from the remote platform.
    """


__all__ = ["IntegrationError"]
