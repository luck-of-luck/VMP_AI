"""Tests for the auth module."""

import os
from unittest import mock

import pytest

from sast_mcp_server.auth import (
    SCOPE_ADMIN,
    SCOPE_CONFIG_WRITE,
    SCOPE_SCAN_READ,
    SCOPE_SCAN_WRITE,
    AuthError,
    AuthProvider,
    create_jwt,
)


def test_auth_disabled():
    with mock.patch.dict(os.environ, clear=True):
        auth = AuthProvider()
        assert not auth.auth_enabled
        assert auth.auth_mode == "none"

        ctx = auth.validate_token("any_token")
        assert ctx.user_id == "anonymous"
        assert ctx.auth_method == "none"
        assert ctx.has_scope(SCOPE_SCAN_READ)


def test_api_key_auth():
    env = {"SAST_MCP_API_KEY": "secret123"}
    with mock.patch.dict(os.environ, env, clear=True):
        auth = AuthProvider()
        assert auth.auth_enabled
        assert auth.auth_mode == "api_key"

        # Valid key
        ctx = auth.validate_token("secret123")
        assert ctx.auth_method == "api_key"
        assert ctx.user_id == "api_key_user"

        # Invalid key
        with pytest.raises(AuthError, match="Invalid API key"):
            auth.validate_token("wrong")


def test_jwt_auth():
    secret = "my_jwt_secret"
    env = {"SAST_MCP_JWT_SECRET": secret}
    with mock.patch.dict(os.environ, env, clear=True):
        auth = AuthProvider()
        assert auth.auth_enabled
        assert auth.auth_mode == "jwt"

        # Valid JWT
        token = create_jwt("testuser", secret, scopes=[SCOPE_SCAN_READ])
        ctx = auth.validate_token(token)

        assert ctx.auth_method == "jwt"
        assert ctx.user_id == "testuser"
        assert ctx.has_scope(SCOPE_SCAN_READ)
        assert not ctx.has_scope(SCOPE_SCAN_WRITE)

        # Invalid signature
        bad_token = token + "bad"
        with pytest.raises(AuthError, match="Invalid JWT signature"):
            auth.validate_token(bad_token)

        # Invalid format
        with pytest.raises(AuthError, match="Invalid JWT format"):
            auth.validate_token("not_a_jwt")


def test_jwt_expiration():
    secret = "my_jwt_secret"
    env = {"SAST_MCP_JWT_SECRET": secret}
    with mock.patch.dict(os.environ, env, clear=True):
        auth = AuthProvider()

        # Expired JWT (expires_in = -10 seconds)
        token = create_jwt("testuser", secret, expires_in=-10)

        with pytest.raises(AuthError, match="JWT token has expired"):
            auth.validate_token(token)


def test_jwt_admin_scope():
    secret = "my_jwt_secret"
    env = {"SAST_MCP_JWT_SECRET": secret}
    with mock.patch.dict(os.environ, env, clear=True):
        auth = AuthProvider()

        token = create_jwt("adminuser", secret, scopes=[SCOPE_ADMIN])
        ctx = auth.validate_token(token)

        # Admin scope implies all scopes
        assert ctx.has_scope(SCOPE_ADMIN)
        assert ctx.has_scope(SCOPE_SCAN_READ)
        assert ctx.has_scope(SCOPE_CONFIG_WRITE)
