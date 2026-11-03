"""Tests for operational HTTP endpoints and reliability primitives.

Covers the things v0.8.0 *claims* (health/readiness/metrics endpoints, the
concurrency cap, scanner-availability reporting) but were previously only
exercised indirectly. The rate limiter and metrics counters themselves are
covered in ``test_v08.py``; here we test the HTTP surface and the aggregator's
concurrency semaphore end-to-end.
"""

import asyncio
import json

import pytest

from sast_mcp_server import aggregator, metrics, server
from sast_mcp_server.scanners.factory import ScannerFactory


class TestOpsEndpoints:
    """The /health, /ready, /metrics custom routes."""

    @pytest.mark.asyncio
    async def test_health_always_ok(self):
        resp = await server._health(None)
        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["status"] == "ok"
        assert "version" in body

    @pytest.mark.asyncio
    async def test_ready_reports_scanner_inventory(self):
        resp = await server._ready(None)
        # 200 when at least one scanner is installed, 503 when none — both valid
        # depending on the test environment; the shape is what we assert.
        assert resp.status_code in (200, 503)
        body = json.loads(resp.body)
        assert body["status"] in ("ready", "degraded")
        assert isinstance(body["scanners_installed"], list)
        assert body["scanners_total"] == len(ScannerFactory.list_scanners())

    @pytest.mark.asyncio
    async def test_metrics_exposition(self):
        metrics.reset()
        metrics.inc("sast_tool_calls_total", labels={"tool": "scan", "status": "ok"})
        resp = await server._metrics(None)
        assert resp.status_code == 200
        text = resp.body.decode()
        assert "sast_uptime_seconds" in text
        assert "sast_tool_calls_total" in text


class TestScannerAvailability:
    """The startup availability probe surfaced to users."""

    @pytest.mark.asyncio
    async def test_partition_is_complete_and_disjoint(self):
        available, missing = await server._check_scanner_availability()
        assert len(available) + len(missing) == len(ScannerFactory.list_scanners())
        assert not (set(available) & set(missing))

    def test_log_availability_does_not_raise(self):
        # Smoke test: the one-line startup log must never crash boot.
        server._log_scanner_availability()

    @pytest.mark.asyncio
    async def test_readiness_is_cached(self, monkeypatch):
        # /ready must not re-probe scanners (a subprocess each) on every call.
        server._readiness_cache = None
        calls = {"n": 0}

        async def _fake_probe():
            calls["n"] += 1
            return ["bandit"]

        monkeypatch.setattr(server, "_probe_installed_scanners", _fake_probe)

        first = await server._installed_scanners()
        second = await server._installed_scanners()
        assert first == second == ["bandit"]
        assert calls["n"] == 1  # second call served from cache

        # Bypassing the cache forces a fresh probe.
        await server._installed_scanners(use_cache=False)
        assert calls["n"] == 2
        server._readiness_cache = None


class _FakeScanner:
    """A scanner that records how many peers run concurrently."""

    def __init__(self, state: dict) -> None:
        self._state = state

    async def check_dependency(self) -> None:
        return None

    async def scan(self, *_args, **_kwargs):
        self._state["current"] += 1
        self._state["max"] = max(self._state["max"], self._state["current"])
        try:
            await asyncio.sleep(0.05)
            return []
        finally:
            self._state["current"] -= 1


class TestConcurrencyCap:
    """The aggregator semaphore must bound in-flight scanners."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_parallelism(self, monkeypatch):
        state = {"current": 0, "max": 0}
        names = [f"fake{i}" for i in range(6)]

        monkeypatch.setattr(ScannerFactory, "list_scanners", staticmethod(lambda: names))
        monkeypatch.setattr(
            ScannerFactory, "get_scanner", staticmethod(lambda _n: _FakeScanner(state))
        )
        # Cap concurrency at 2 regardless of the 6 scanners fanned out.
        monkeypatch.setattr(aggregator, "_scan_semaphore", asyncio.Semaphore(2))

        findings, used, skipped = await aggregator.run_all_scanners("/tmp", timeout=5)

        assert state["max"] <= 2
        assert len(used) == 6
        assert findings == []

    @pytest.mark.asyncio
    async def test_unlimited_when_semaphore_disabled(self, monkeypatch):
        state = {"current": 0, "max": 0}
        names = [f"fake{i}" for i in range(5)]

        monkeypatch.setattr(ScannerFactory, "list_scanners", staticmethod(lambda: names))
        monkeypatch.setattr(
            ScannerFactory, "get_scanner", staticmethod(lambda _n: _FakeScanner(state))
        )
        monkeypatch.setattr(aggregator, "_scan_semaphore", None)

        await aggregator.run_all_scanners("/tmp", timeout=5)

        # With no cap all five should overlap.
        assert state["max"] == 5
