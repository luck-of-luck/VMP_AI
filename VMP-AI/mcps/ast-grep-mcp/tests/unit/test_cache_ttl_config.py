"""Tests for CACHE_TTL using correct TTL_SECONDS constant."""

from ast_grep_mcp.constants import CacheDefaults
from ast_grep_mcp.core.config import CACHE_TTL


class TestCacheTTLConfig:
    def test_cache_ttl_uses_ttl_seconds(self):
        """CACHE_TTL should use TTL_SECONDS (3600), not CLEANUP_INTERVAL_SECONDS (300)."""
        assert CACHE_TTL == CacheDefaults.TTL_SECONDS

    def test_cache_ttl_not_cleanup_interval(self):
        assert CACHE_TTL != CacheDefaults.CLEANUP_INTERVAL_SECONDS

    def test_ttl_is_one_hour(self):
        assert CACHE_TTL == 3600
