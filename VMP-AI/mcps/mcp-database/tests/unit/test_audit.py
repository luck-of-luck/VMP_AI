import hashlib
import json
import os
import stat

from mcp_database.audit import AuditLogger, verify_chain


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_record_happy(tmp_path):
    path = tmp_path / "nested" / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="pg", tool="db_write_query", query="DELETE FROM t", ok=True, affected=3, duration_ms=12.34)

    entries = read_lines(path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["v"] == 1
    assert entry["connection"] == "pg"
    assert entry["tool"] == "db_write_query"
    assert entry["affected"] == 3
    assert entry["duration_ms"] == 12.3
    assert entry["ok"] is True
    assert entry["dry_run"] is False
    assert "ts" in entry


def test_file_mode_is_owner_only(tmp_path):
    path = tmp_path / "audit.log"
    AuditLogger(path).record(connection="c", tool="t", query="q", ok=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_appends_and_flags(tmp_path):
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="c", tool="db_write_query", query="q1", ok=True, dry_run=True)
    logger.record(connection="c", tool="db_admin_kill", query={"target_id": "42"}, ok=False, error="boom")
    first, second = read_lines(path)
    assert first["dry_run"] is True
    assert second["ok"] is False
    assert second["error"] == "boom"
    assert second["query"] == {"target_id": "42"}


def test_append_does_not_rechmod_existing_file(tmp_path):
    """chmod 0600 happens only when the log file is created; appends keep whatever mode the owner set."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="c", tool="t", query="q", ok=True)
    os.chmod(path, 0o644)
    logger.record(connection="c", tool="t", query="q", ok=True)
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert len(read_lines(path)) == 2


def test_affected_zero_is_logged_and_none_omitted(tmp_path):
    """affected=0 is real information and lands in the entry; affected=None omits the key entirely."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="c", tool="t", query="q", ok=True, affected=0)
    logger.record(connection="c", tool="t", query="q", ok=True, affected=None)
    first, second = read_lines(path)
    assert first["affected"] == 0
    assert "affected" not in second


def test_error_message_password_is_redacted(tmp_path):
    path = tmp_path / "audit.log"
    AuditLogger(path).record(
        connection="c",
        tool="t",
        query="q",
        ok=False,
        error="connect failed for postgresql://app:hunter2@db:5432/x",
    )
    (entry,) = read_lines(path)
    assert "hunter2" not in entry["error"]
    assert "app:***@" in entry["error"]


def test_absurd_query_payloads_still_serialize(tmp_path):
    path = tmp_path / "audit.log"
    AuditLogger(path).record(connection="c", tool="t", query={"emoji": "😀", "bytes": b"\x00\x01"}, ok=True)
    (entry,) = read_lines(path)
    assert entry["query"]["emoji"] == "😀"
    assert verify_chain(path) is None


def test_entries_are_hash_chained(tmp_path):
    """Each entry's prev is the sha256 of the previous line; the first entry links to the empty genesis."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="c", tool="t", query="q1", ok=True)
    logger.record(connection="c", tool="t", query="q2", ok=True)
    first_line, _ = path.read_text().splitlines()
    first, second = read_lines(path)
    assert first["prev"] == ""
    assert second["prev"] == hashlib.sha256(first_line.encode()).hexdigest()
    assert verify_chain(path) is None


def test_chain_resumes_across_logger_instances(tmp_path):
    """A new AuditLogger on an existing file continues the chain instead of restarting from genesis."""
    path = tmp_path / "audit.log"
    AuditLogger(path).record(connection="c", tool="t", query="q1", ok=True)
    AuditLogger(path).record(connection="c", tool="t", query="q2", ok=True)
    assert verify_chain(path) is None
    _, second = read_lines(path)
    assert second["prev"] != ""


def test_tampering_breaks_the_chain(tmp_path):
    """Editing any recorded line invalidates the link of the entry after it."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    logger.record(connection="c", tool="t", query="DELETE FROM a WHERE id = ?", ok=True)
    logger.record(connection="c", tool="t", query="q2", ok=True)
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace("DELETE", "SELECT")
    path.write_text("\n".join(lines) + "\n")
    assert verify_chain(path) == 1


def test_rotation_starts_a_fresh_chained_file(tmp_path):
    """Past max_bytes the log rolls to .1 and the new file restarts the chain from genesis, both intact."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path, max_bytes=200)
    for i in range(20):
        logger.record(connection="c", tool="t", query=f"q{i}", ok=True)
    rotated = path.with_suffix(".log.1")
    assert rotated.exists()
    assert verify_chain(rotated) is None
    assert verify_chain(path) is None
    assert read_lines(path)[0]["prev"] == ""


def test_no_rotation_without_max_bytes(tmp_path):
    """With max_bytes unset the log grows in place — rotation is strictly opt-in."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    for i in range(50):
        logger.record(connection="c", tool="t", query=f"q{i}", ok=True)
    assert not path.with_suffix(".log.1").exists()
    assert len(read_lines(path)) == 50


def test_deleting_an_entry_breaks_the_chain(tmp_path):
    """Removing a middle entry is detectable — the next entry no longer links to its predecessor."""
    path = tmp_path / "audit.log"
    logger = AuditLogger(path)
    for query in ("q1", "q2", "q3"):
        logger.record(connection="c", tool="t", query=query, ok=True)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert verify_chain(path) == 1


class TestChainEdgeCases:
    def test_last_line_of_blank_file_is_none(self, tmp_path):
        """A file holding only blank lines resumes the chain from genesis."""
        path = tmp_path / "audit.log"
        path.write_text("\n\n \n")
        from mcp_database.audit import _last_line

        assert _last_line(path) is None

    def test_verify_chain_skips_blank_lines(self, tmp_path):
        """Blank lines inside the log are ignored by chain verification."""
        import json

        from mcp_database.audit import _line_hash, verify_chain

        first = json.dumps({"prev": "", "op": 1})
        second = json.dumps({"prev": _line_hash(first), "op": 2})
        path = tmp_path / "audit.log"
        path.write_text(f"{first}\n\n{second}\n")
        assert verify_chain(path) is None
