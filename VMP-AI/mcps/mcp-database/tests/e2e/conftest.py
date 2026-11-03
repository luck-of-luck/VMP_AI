import pytest

from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .helpers import REGISTRY, FakeAdapter


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def audit_path(tmp_path):
    return tmp_path / "audit.log"


@pytest.fixture
def mcp_server(monkeypatch, audit_path):
    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: FakeAdapter(cfg))
    return build_server(dict(REGISTRY), audit=AuditLogger(audit_path))
