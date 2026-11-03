import argparse
from pathlib import Path

import pytest

from mcp_database.entry import main

ENV_VARS = (
    "ENGINE_TYPE",
    "URI",
    "NAME",
    "MODE",
    "TIMEOUT",
    "ROW_LIMIT",
    "PASSWORD_ENV",
    "WRITE_OPS",
    "DATABASE_MODES",
    "REDACT_FIELDS",
    "AUDIT_LOG",
    "LOG_LEVEL",
    "MCPDB_CONNECTIONS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def served(monkeypatch):
    calls = {}

    def fake_build_server(registry, audit, enabled_tools=None):
        calls["registry"] = registry
        calls["audit"] = audit
        calls["enabled_tools"] = enabled_tools
        return argparse.Namespace(run=lambda: calls.setdefault("ran", True))

    monkeypatch.setattr("mcp_database.entry.build_server", fake_build_server)
    return calls


class TestMain:
    def test_happy_serves_exactly_one_connection(self, monkeypatch, served):
        monkeypatch.setenv("ENGINE_TYPE", "postgres")
        monkeypatch.setenv("URI", "postgresql://u@h/app")
        monkeypatch.setenv("NAME", "pg_app")
        monkeypatch.setenv("MODE", "read_write")
        main()
        assert list(served["registry"]) == ["pg_app"]
        assert served["registry"]["pg_app"].access_mode == "read_write"
        assert served["ran"]

    def test_happy_audit_log_path_from_env(self, monkeypatch, served, tmp_path):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv("AUDIT_LOG", str(tmp_path / "audit.jsonl"))
        main()
        assert served["audit"].path == Path(tmp_path / "audit.jsonl")

    def test_happy_audit_max_bytes_from_env(self, monkeypatch, served):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv("AUDIT_MAX_BYTES", "1048576")
        main()
        assert served["audit"].max_bytes == 1048576

    def test_sad_audit_max_bytes_non_integer_exits(self, monkeypatch, served, capsys):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv("AUDIT_MAX_BYTES", "big")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "AUDIT_MAX_BYTES" in capsys.readouterr().err

    def test_happy_tools_env_reaches_build_server(self, monkeypatch, served):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv("TOOLS", '["db_read_query", "db_schema_connections"]')
        main()
        assert served["enabled_tools"] == frozenset({"db_read_query", "db_schema_connections"})

    def test_happy_no_tools_env_enables_all(self, monkeypatch, served):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        main()
        assert served["enabled_tools"] is None

    @pytest.mark.parametrize(
        ("var", "value"),
        [("TOOLS", '["nope"]'), ("TOOLS", "[]"), ("TOOLS", "not json"), ("DISABLE_TOOLS", '["ghost"]')],
    )
    def test_sad_invalid_tools_env_exits(self, monkeypatch, served, capsys, var, value):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv(var, value)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2

    def test_sigterm_maps_to_graceful_shutdown(self, monkeypatch, served):
        import signal

        original = signal.getsignal(signal.SIGTERM)
        monkeypatch.setenv("URI", "mysql://u@h/db")
        try:
            main()
            assert signal.getsignal(signal.SIGTERM) is signal.default_int_handler
        finally:
            signal.signal(signal.SIGTERM, original)

    def test_sad_no_connection_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "URI is required" in capsys.readouterr().err

    def test_sad_engine_uri_mismatch_exits(self, monkeypatch, capsys):
        monkeypatch.setenv("ENGINE_TYPE", "postgres")
        monkeypatch.setenv("URI", "mysql://u@h/db")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "does not match ENGINE_TYPE" in capsys.readouterr().err

    def test_sad_legacy_connections_var_alone_is_not_enough(self, monkeypatch, capsys):
        monkeypatch.setenv("MCPDB_CONNECTIONS", '[{"name": "a", "uri": "mysql://u@h/db"}]')
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "URI is required" in capsys.readouterr().err

    @pytest.mark.parametrize("level", ["banana", "🚀", "DEBUG; rm -rf /"])
    def test_absurd_log_level_exits(self, monkeypatch, capsys, level):
        monkeypatch.setenv("URI", "mysql://u@h/db")
        monkeypatch.setenv("LOG_LEVEL", level)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "LOG_LEVEL" in capsys.readouterr().err


def test_sigterm_install_off_main_thread_is_a_noop(monkeypatch):
    """When signal.signal raises ValueError (non-main thread), shutdown install degrades silently."""
    import signal as signal_module

    from mcp_database.entry import _install_graceful_shutdown

    def boom(signum, handler):
        raise ValueError("signal only works in main thread")

    monkeypatch.setattr(signal_module, "signal", boom)
    _install_graceful_shutdown()
