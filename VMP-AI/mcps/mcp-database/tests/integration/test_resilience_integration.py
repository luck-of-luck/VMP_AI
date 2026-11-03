"""Failure injection and load: the server must degrade cleanly and recover without a process restart."""

import asyncio
import json
import socket

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .conftest import PG_IMAGE, make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def restartable_pg():
    """A dedicated postgres container this module may stop and start (the shared session one must stay up).

    The host port is pinned: Docker reassigns random published ports on restart, but a real local
    database comes back on the same address — which is exactly the scenario under test.
    """
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(PG_IMAGE, username="test", password="test", dbname="test")
    container.with_bind_ports(5432, _free_port())
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield container, f"postgresql://test:test@{host}:{port}/test"


async def _wait_until_up(adapter, attempts=60):
    """Poll ping until the restarted database accepts connections again, failing after ~30s."""
    for _ in range(attempts):
        try:
            await adapter.ping()
            return
        except Exception:
            await asyncio.sleep(0.5)
    pytest.fail("database did not come back after restart")


async def test_adapter_survives_database_restart(restartable_pg):
    """A database bounce mid-session gives clean errors while down and full recovery after, no process restart."""
    container, uri = restartable_pg
    adapter = PostgresAdapter(make_cfg("bounce", uri))
    try:
        (await adapter._ensure_pool()).timeout = 3
        assert await adapter.read("SELECT 1 AS ok", None, 1) == [{"ok": 1}]

        docker_container = container.get_wrapped_container()
        docker_container.stop()
        with pytest.raises(Exception, match=r"(?i)connect|closed|refused|terminat"):
            await adapter.read("SELECT 1 AS ok", None, 1)

        docker_container.start()
        await _wait_until_up(adapter)
        assert await adapter.read("SELECT 1 AS ok", None, 1) == [{"ok": 1}]
    finally:
        await adapter.close()


async def test_concurrent_read_burst_on_tiny_pool(restartable_pg, tmp_path):
    """25 concurrent reads through the server on a pool of 2 all succeed — requests queue, never deadlock."""
    _, uri = restartable_pg
    cfg = make_cfg("target", uri, pool_size=2)
    server = build_server({"target": cfg}, audit=AuditLogger(tmp_path / "audit.log"))
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        results = await asyncio.gather(
            *(client.call_tool("db_read_query", {"conn": "target", "query": f"SELECT {i} AS n"}) for i in range(25))
        )
    for result in results:
        assert not result.isError, result.content[0].text
    values = sorted(json.loads(r.content[0].text)["rows"][0]["n"] for r in results)
    assert values == list(range(25))
