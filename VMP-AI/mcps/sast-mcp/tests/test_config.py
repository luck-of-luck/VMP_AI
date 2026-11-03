"""Tests for the central validated configuration (config.py)."""

from sast_mcp_server.config import Settings


def test_defaults_when_env_unset(monkeypatch):
    for var in [
        "SAST_MCP_TIMEOUT",
        "SAST_MCP_LOG_LEVEL",
        "SAST_MCP_CACHE_TTL",
        "SAST_MCP_HTTP_RETRIES",
        "SAST_MCP_HTTP_TIMEOUT",
        "SAST_MCP_CACHE_MAX_SCANS",
    ]:
        monkeypatch.delenv(var, raising=False)
    s = Settings.from_env()
    assert s.scan_timeout == 300
    assert s.log_level == "INFO"
    assert s.cache_ttl == 86400
    assert s.http_retries == 3
    assert s.http_timeout == 60.0
    assert s.cache_max_scans == 200


def test_valid_overrides(monkeypatch):
    monkeypatch.setenv("SAST_MCP_TIMEOUT", "120")
    monkeypatch.setenv("SAST_MCP_LOG_LEVEL", "debug")
    monkeypatch.setenv("SAST_MCP_HTTP_RETRIES", "5")
    s = Settings.from_env()
    assert s.scan_timeout == 120
    assert s.log_level == "DEBUG"
    assert s.http_retries == 5


def test_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("SAST_MCP_TIMEOUT", "not-an-int")
    monkeypatch.setenv("SAST_MCP_LOG_LEVEL", "LOUD")
    s = Settings.from_env()
    assert s.scan_timeout == 300  # bad int -> default
    assert s.log_level == "INFO"  # invalid level -> default


def test_bounds_are_clamped(monkeypatch):
    monkeypatch.setenv("SAST_MCP_TIMEOUT", "0")  # below min 1
    monkeypatch.setenv("SAST_MCP_HTTP_RETRIES", "999")  # above max 10
    s = Settings.from_env()
    assert s.scan_timeout == 1
    assert s.http_retries == 10


def test_live_secret_accessors(monkeypatch):
    monkeypatch.setenv("SAST_MCP_API_KEY", "  k  ")
    monkeypatch.setenv("SAST_MCP_JWT_SECRET", "secret")
    s = Settings.from_env()
    assert s.api_key == "k"
    assert s.jwt_secret == "secret"
    # Live read — clearing the env reflects immediately.
    monkeypatch.delenv("SAST_MCP_API_KEY", raising=False)
    assert s.api_key == ""
