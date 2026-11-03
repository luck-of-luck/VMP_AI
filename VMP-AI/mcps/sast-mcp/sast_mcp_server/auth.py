"""JWT-based authentication for remote SAST MCP Server deployments.

Supports two modes:
1. Simple mode: Static API key via SAST_MCP_API_KEY (backward-compatible)
2. JWT mode: JWT bearer token validation via SAST_MCP_JWT_SECRET

For local stdio transport, authentication is skipped (local trust model).
"""

import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass, field

from sast_mcp_server.config import get_settings

logger = logging.getLogger(__name__)

# Scopes for authorization
SCOPE_SCAN_READ = "scan:read"
SCOPE_SCAN_WRITE = "scan:write"
SCOPE_CONFIG_WRITE = "config:write"
SCOPE_ADMIN = "admin"

ALL_SCOPES = {SCOPE_SCAN_READ, SCOPE_SCAN_WRITE, SCOPE_CONFIG_WRITE, SCOPE_ADMIN}
DEFAULT_SCOPES = {SCOPE_SCAN_READ, SCOPE_SCAN_WRITE}


@dataclass
class AuthContext:
    """Authenticated user context after token validation."""

    user_id: str
    scopes: set[str] = field(default_factory=lambda: DEFAULT_SCOPES.copy())
    expires_at: float = 0.0  # Unix timestamp, 0 = no expiry
    auth_method: str = "none"  # "api_key", "jwt", or "none"

    def has_scope(self, scope: str) -> bool:
        """Check if this context has a specific scope."""
        return SCOPE_ADMIN in self.scopes or scope in self.scopes

    @property
    def is_expired(self) -> bool:
        """Check if this token has expired."""
        if self.expires_at == 0.0:
            return False
        return time.time() > self.expires_at


class AuthProvider:
    """Handles authentication for the MCP server.

    Reads configuration from environment variables:
    - SAST_MCP_API_KEY: Simple static API key (backward-compatible)
    - SAST_MCP_JWT_SECRET: HMAC-SHA256 secret for JWT validation

    If neither is set, auth is disabled (suitable for local stdio transport).
    """

    def __init__(self):
        _settings = get_settings()
        self.api_key = _settings.api_key
        self.jwt_secret = _settings.jwt_secret
        self.auth_enabled = bool(self.api_key or self.jwt_secret)

        if self.jwt_secret:
            self.auth_mode = "jwt"
        elif self.api_key:
            self.auth_mode = "api_key"
        else:
            self.auth_mode = "none"

    def validate_token(self, token: str) -> AuthContext:
        """Validate a bearer token and return an AuthContext.

        Args:
            token: The bearer token string (API key or JWT).

        Returns:
            AuthContext with user info and scopes.

        Raises:
            AuthError: If the token is invalid or expired.
        """
        if not self.auth_enabled:
            return AuthContext(
                user_id="anonymous",
                scopes=ALL_SCOPES.copy(),
                auth_method="none",
            )

        # Try JWT first if configured
        if self.jwt_secret:
            return self._validate_jwt(token)

        # Fall back to simple API key
        if self.api_key:
            return self._validate_api_key(token)

        return AuthContext(
            user_id="anonymous",
            scopes=ALL_SCOPES.copy(),
            auth_method="none",
        )

    def _validate_api_key(self, token: str) -> AuthContext:
        """Validate a static API key."""
        if not hmac.compare_digest(token.strip(), self.api_key):
            raise AuthError("Invalid API key")

        return AuthContext(
            user_id="api_key_user",
            scopes=ALL_SCOPES.copy(),
            auth_method="api_key",
        )

    def _validate_jwt(self, token: str) -> AuthContext:
        """Validate a JWT token using HMAC-SHA256.

        JWT format: header.payload.signature
        - header: {"alg": "HS256", "typ": "JWT"}
        - payload: {"sub": user_id, "scopes": [...], "exp": unix_timestamp}
        """
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise AuthError("Invalid JWT format: expected 3 parts")

        try:
            header_b64, payload_b64, signature_b64 = parts

            # Verify signature
            signing_input = f"{header_b64}.{payload_b64}"
            expected_sig = hmac.new(
                self.jwt_secret.encode("utf-8"),
                signing_input.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            actual_sig = _b64decode(signature_b64)

            if not hmac.compare_digest(expected_sig, actual_sig):
                raise AuthError("Invalid JWT signature")

            # Decode payload
            payload = json.loads(_b64decode(payload_b64).decode("utf-8"))

        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            raise AuthError(f"Invalid JWT payload: {e}") from e

        # Check expiration
        exp = payload.get("exp", 0)
        if exp and time.time() > exp:
            raise AuthError("JWT token has expired")

        # Extract scopes
        scope_list = payload.get("scopes", list(DEFAULT_SCOPES))
        scopes = set(scope_list) & ALL_SCOPES
        if not scopes:
            scopes = DEFAULT_SCOPES.copy()

        return AuthContext(
            user_id=str(payload.get("sub", "jwt_user")),
            scopes=scopes,
            expires_at=float(exp) if exp else 0.0,
            auth_method="jwt",
        )

    def get_status(self) -> dict:
        """Return auth configuration status (for logging/resources)."""
        return {
            "enabled": self.auth_enabled,
            "mode": self.auth_mode,
            "api_key_configured": bool(self.api_key),
            "jwt_configured": bool(self.jwt_secret),
        }


class AuthError(Exception):
    """Raised when authentication fails."""


def authorize(
    provider: "AuthProvider", token: str | None, required_scope: str
) -> AuthContext:
    """Validate a token and confirm it grants ``required_scope``.

    When auth is disabled (local stdio trust model) this returns an anonymous
    context with all scopes. Otherwise the token must be present, valid,
    unexpired, and carry the required scope (or ``admin``).

    Args:
        provider: The configured :class:`AuthProvider`.
        token: The bearer token presented by the caller, or ``None``.
        required_scope: The scope the operation requires.

    Returns:
        The validated :class:`AuthContext`.

    Raises:
        AuthError: If the token is missing, invalid, expired, or under-scoped.
    """
    if not provider.auth_enabled:
        return AuthContext(
            user_id="anonymous", scopes=ALL_SCOPES.copy(), auth_method="none"
        )

    if not token:
        raise AuthError("Missing bearer token")

    ctx = provider.validate_token(token)
    if ctx.is_expired:
        raise AuthError("Token has expired")
    if not ctx.has_scope(required_scope):
        raise AuthError(f"Token lacks required scope '{required_scope}'")
    return ctx


def create_jwt(
    user_id: str,
    secret: str,
    scopes: list[str] | None = None,
    expires_in: int = 3600,
) -> str:
    """Create a JWT token (utility for testing and token generation).

    Args:
        user_id: The user identifier (becomes 'sub' claim).
        secret: HMAC-SHA256 secret key.
        scopes: List of scope strings. Defaults to scan:read + scan:write.
        expires_in: Token lifetime in seconds (default 1 hour).

    Returns:
        A signed JWT token string.
    """
    if scopes is None:
        scopes = list(DEFAULT_SCOPES)

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "scopes": scopes,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }

    header_b64 = _b64encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64encode(json.dumps(payload).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _b64encode(data: bytes) -> str:
    """URL-safe base64 encode without padding."""
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(s: str) -> bytes:
    """URL-safe base64 decode with padding restoration."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return urlsafe_b64decode(s)
