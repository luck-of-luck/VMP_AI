"""Pure summarizers: turn raw adapter diagnostic sections into human findings and next-tool hints."""

from __future__ import annotations

from typing import Any

from ..helpers import tls_probe


def _summarize_diagnosis(sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn raw diagnosis sections into human findings and suggested next tools (pure, section-shape tolerant)."""
    findings: list[str] = []
    next_steps: list[str] = []

    ops = sections.get("active_ops")
    if isinstance(ops, list):
        slow = [o for o in ops if isinstance(o.get("duration_ms"), int | float) and o["duration_ms"] >= 1000]
        if slow:
            findings.append(f"{len(slow)} operation(s) running 1s or longer")
            next_steps.append("db_perf_explain on the slow query to see its plan")
        idle_txn = [o for o in ops if isinstance(o.get("xact_age_ms"), int | float) and o["xact_age_ms"] >= 60_000]
        if idle_txn:
            findings.append(f"{len(idle_txn)} transaction(s) open 60s or longer (blocks vacuum / holds locks)")

    blocking = sections.get("blocking")
    if isinstance(blocking, list) and blocking:
        findings.append(f"{len(blocking)} lock wait(s) detected")
        next_steps.append("db_admin_kill on the blocking session if it is safe to cancel")

    health = sections.get("health")
    if isinstance(health, dict):
        conns = health.get("connections")
        if isinstance(conns, dict):
            current, maximum = conns.get("current"), conns.get("max")
            if isinstance(current, int) and isinstance(maximum, int) and maximum and current / maximum >= 0.8:
                findings.append(f"connection pool near saturation ({current}/{maximum})")

    top = sections.get("top_queries")
    if isinstance(top, list) and top:
        next_steps.append("db_perf_explain on the top query from top_queries")

    if not findings:
        findings.append("no obvious contention: no long operations, lock waits or saturation detected")
    return findings, next_steps


def _recommended_lists(rows: float) -> float:
    """pgvector's ivfflat sizing rule: rows/1000 up to 1M rows, sqrt(rows) beyond."""
    return rows / 1000 if rows <= 1_000_000 else rows**0.5


def _vector_columns(indexes: Any, columns: Any) -> tuple[list[str], list[str], dict[tuple[Any, Any], Any]]:
    """Vector columns lacking a covering index, plus a table→approx_rows map for later sizing checks."""
    findings: list[str] = []
    next_steps: list[str] = []
    rows_by_table: dict[tuple[Any, Any], Any] = {}
    if not isinstance(columns, list):
        return findings, next_steps, rows_by_table

    indexed = set()
    if isinstance(indexes, list):
        indexed = {(i.get("schema"), i.get("table"), i.get("column")) for i in indexes if isinstance(i, dict)}
    unindexed = [
        c for c in columns if isinstance(c, dict) and (c.get("schema"), c.get("table"), c.get("column")) not in indexed
    ]
    if unindexed:
        names = ", ".join(f"{c.get('table')}.{c.get('column')}" for c in unindexed[:5])
        findings.append(f"{len(unindexed)} vector column(s) without a vector index ({names}): every search scans")
        next_steps.append("db_write_search_index action=create on the unindexed column")
    rows_by_table = {(c.get("schema"), c.get("table")): c.get("approx_rows") for c in columns if isinstance(c, dict)}
    return findings, next_steps, rows_by_table


def _ivfflat_lists_finding(entry: dict[str, Any], rows_by_table: dict[tuple[Any, Any], Any]) -> str | None:
    """Warn when an ivfflat index's lists= is far from the value its row count suggests."""
    options = entry.get("options")
    if entry.get("method") != "ivfflat" or not isinstance(options, list):
        return None
    values = (str(o).split("=", 1)[1] for o in options if str(o).startswith("lists="))
    lists = next((int(v) for v in values if v.isdigit()), None)
    rows = rows_by_table.get((entry.get("schema"), entry.get("table")))
    if lists and isinstance(rows, int | float) and rows > 0:
        recommended = _recommended_lists(rows)
        if lists < recommended / 4 or lists > recommended * 4:
            return (
                f"index '{entry.get('index')}' has lists={lists} but ~{int(rows)} rows suggest "
                f"~{int(recommended)}; recall/speed may suffer"
            )
    return None


def _vector_index_health(indexes: Any, rows_by_table: dict[tuple[Any, Any], Any]) -> list[str]:
    """Per-index findings: invalid builds, not-yet-queryable indexes and ivfflat mis-sizing."""
    findings: list[str] = []
    if not isinstance(indexes, list):
        return findings
    for entry in indexes:
        if not isinstance(entry, dict):
            continue
        if entry.get("valid") is False:
            findings.append(f"index '{entry.get('index')}' is invalid (failed or aborted build); drop and recreate")
        if entry.get("queryable") is False or entry.get("status") not in (None, "READY"):
            findings.append(
                f"index '{entry.get('index')}' is not queryable yet (status: {entry.get('status')}); "
                "wait for the build to finish"
            )
        sizing = _ivfflat_lists_finding(entry, rows_by_table)
        if sizing:
            findings.append(sizing)
    return findings


def _vector_settings(sections: dict[str, Any]) -> list[str]:
    """Global vector findings: the low ivfflat.probes default and in-flight index builds."""
    findings: list[str] = []
    settings = sections.get("settings")
    if isinstance(settings, dict) and settings.get("ivfflat.probes") in (1, "1"):
        findings.append("ivfflat.probes is 1 (the default): recall may be low on ivfflat indexes")
    builds = sections.get("index_builds")
    if isinstance(builds, list) and builds:
        findings.append(f"{len(builds)} index build(s) in progress")
    return findings


def _summarize_vector(sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn raw vector-stats sections into human findings and next tools (pure, section-shape tolerant)."""
    indexes = sections.get("vector_indexes")
    columns = sections.get("vector_columns")
    findings, next_steps, rows_by_table = _vector_columns(indexes, columns)
    findings += _vector_index_health(indexes, rows_by_table)
    findings += _vector_settings(sections)

    if not findings:
        findings.append("vector search looks healthy: indexes present, queryable and no builds in flight")
    else:
        next_steps.append("db_perf_explain on a representative search to confirm the index is used")
    return findings, next_steps


def _cluster_repl_pg(repl: dict[str, Any]) -> tuple[list[str], list[str]]:
    """PostgreSQL streaming-replication findings: missing replicas, replica lag/state, paused replay."""
    findings: list[str] = []
    next_steps: list[str] = []
    role = repl.get("role")
    if role == "standalone" or (role in ("source", "primary") and not repl.get("replicas")):
        findings.append("no active replication: this server has no connected replicas")

    replicas = repl.get("replicas")
    if isinstance(replicas, list):
        for replica in replicas:
            if not isinstance(replica, dict):
                continue
            name = replica.get("application_name") or replica.get("client_addr") or "replica"
            lag_bytes = replica.get("replay_lag_bytes")
            if isinstance(lag_bytes, int | float) and lag_bytes > 64 * 1024 * 1024:
                findings.append(f"{name} is {int(lag_bytes)} bytes behind on WAL replay")
            state = replica.get("state")
            if isinstance(state, str) and state != "streaming":
                findings.append(f"{name} is in state '{state}' (expected 'streaming')")

    age = repl.get("replay_age_s")
    if isinstance(age, int | float) and age >= 10:
        findings.append(f"this replica last replayed a transaction {int(age)}s ago")

    if repl.get("replay_paused") is True:
        findings.append("WAL replay is paused on this standby: it accumulates lag until resumed")
        next_steps.append("db_admin_cluster action=resume_replay to resume WAL replay")
    return findings, next_steps


def _cluster_repl_mysql(repl: dict[str, Any]) -> tuple[list[str], list[str]]:
    """MySQL/MariaDB replica findings: lost master link, stopped threads, lag and last error."""
    findings: list[str] = []
    next_steps: list[str] = []
    link = repl.get("master_link_status")
    if repl.get("role") == "slave" and isinstance(link, str) and link != "up":
        findings.append(f"replica lost its master link (status '{link}'): it serves stale data")

    status = repl.get("status")
    if isinstance(status, list):
        for row in status:
            if not isinstance(row, dict):
                continue
            stopped = row.get("Replica_IO_Running") not in (None, "Yes") or row.get("Replica_SQL_Running") not in (
                None,
                "Yes",
            )
            if stopped:
                findings.append("a replication thread is stopped (Replica_IO/SQL_Running is not 'Yes')")
                next_steps.append("db_admin_cluster action=start_replica once the cause is fixed")
            behind = row.get("Seconds_Behind_Source")
            if isinstance(behind, int | float) and behind >= 10:
                findings.append(f"replica is {int(behind)}s behind the source")
            if row.get("Last_Error"):
                findings.append(f"replication error: {row['Last_Error']}")
    return findings, next_steps


def _cluster_repl_mongo(repl: dict[str, Any]) -> list[str]:
    """MongoDB replica-set findings: no primary, unhealthy or unexpected member states, secondary lag."""
    findings: list[str] = []
    members = repl.get("members")
    if isinstance(members, list) and members:
        if not any(isinstance(m, dict) and m.get("state") == "PRIMARY" for m in members):
            findings.append("replica set has no PRIMARY (election pending or quorum lost)")
        for member in members:
            if not isinstance(member, dict):
                continue
            if member.get("health") == 0:
                findings.append(f"member {member.get('name')} is unhealthy (health=0)")
            state = member.get("state")
            if state not in (None, "PRIMARY", "SECONDARY", "ARBITER"):
                findings.append(f"member {member.get('name')} is in state '{state}'")
            lag = member.get("lag_seconds")
            if isinstance(lag, int | float) and lag >= 10:
                findings.append(f"member {member.get('name')} is {int(lag)}s behind the primary")
    return findings


def _cluster_health(health: Any) -> list[str]:
    """Connection-pool saturation finding from the health section."""
    if isinstance(health, dict):
        conns = health.get("connections")
        if isinstance(conns, dict):
            current, maximum = conns.get("current"), conns.get("max")
            if isinstance(current, int) and isinstance(maximum, int) and maximum and current / maximum >= 0.8:
                return [f"connection pool near saturation ({current}/{maximum})"]
    return []


def _summarize_cluster(sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn replication/health sections into human findings and next tools (pure, section-shape tolerant)."""
    findings: list[str] = []
    next_steps: list[str] = []

    repl = sections.get("replication")
    if isinstance(repl, dict):
        for part_findings, part_next in (_cluster_repl_pg(repl), _cluster_repl_mysql(repl)):
            findings += part_findings
            next_steps += part_next
        findings += _cluster_repl_mongo(repl)
    findings += _cluster_health(sections.get("health"))

    if findings:
        next_steps.append("db_perf_replication for the raw replication state")
    else:
        findings.append("cluster looks healthy: replication running with no lag above thresholds")
    return findings, next_steps


def _pct(numerator: Any, denominator: Any) -> float | None:
    """Ratio of two numbers, or None when not computable (missing/zero denominator)."""
    if isinstance(numerator, int | float) and isinstance(denominator, int | float) and denominator:
        return numerator / denominator
    return None


def _storage_capacity(sections: dict[str, Any]) -> list[str]:
    """Near-full disk/memory and short-oplog findings (the 'running out of room' signals)."""
    findings: list[str] = []
    db = sections.get("db")
    if isinstance(db, dict):
        fs = _pct(db.get("fs_used_bytes"), db.get("fs_total_bytes"))
        if fs is not None and fs >= 0.8:
            findings.append(f"filesystem is {round(fs * 100)}% full")
    oplog = sections.get("oplog")
    if isinstance(oplog, dict) and isinstance(oplog.get("window_hours"), int | float) and oplog["window_hours"] < 1:
        findings.append(f"oplog window is only {oplog['window_hours']}h: a slow secondary could fall off it")

    memory = sections.get("memory")
    if isinstance(memory, dict):
        used = _pct(memory.get("used_bytes"), memory.get("max_bytes"))
        if used is not None and used >= 0.8:
            findings.append(f"memory is {round(used * 100)}% of maxmemory")
        frag = memory.get("fragmentation_ratio")
        if isinstance(frag, int | float) and frag >= 1.5:
            findings.append(f"memory fragmentation ratio is {frag} (>=1.5 wastes RAM)")
    return findings


def _storage_reclaimable(sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Reclaimable-space findings: temp spill, dead-tuple bloat, binlog retention, SQLite freelist."""
    findings: list[str] = []
    next_steps: list[str] = []
    temp = sections.get("temp")
    if isinstance(temp, dict) and isinstance(temp.get("temp_bytes"), int | float) and temp["temp_bytes"] > 1 << 30:
        findings.append(f"{int(temp['temp_bytes'])} bytes of temp files spilled: consider raising work_mem")
        next_steps.append("db_perf_config_check for the work_mem/sort signals")

    dead = sections.get("dead_tuples")
    if isinstance(dead, list):
        for row in dead:
            ratio = _pct(row.get("n_dead_tup"), row.get("n_live_tup"))
            if ratio is not None and ratio >= 0.2:
                findings.append(f"{row.get('relation')} is {round(ratio * 100)}% dead tuples (bloat)")
                next_steps.append("db_admin_maintain to reclaim space")
                break

    logs = sections.get("binary_logs")
    if isinstance(logs, dict) and isinstance(logs.get("bytes"), int) and logs["bytes"] > 5 * (1 << 30):
        findings.append(f"binary logs hold {logs['bytes']} bytes: check binlog retention")

    file = sections.get("file")
    if (
        isinstance(file, dict)
        and isinstance(file.get("freelist_ratio"), int | float)
        and file["freelist_ratio"] >= 0.25
    ):
        findings.append(f"{round(file['freelist_ratio'] * 100)}% of pages are free: VACUUM would shrink the file")
        next_steps.append("db_admin_maintain action=vacuum")
    return findings, next_steps


def _summarize_storage(engine: str, sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn raw storage sections into findings about near-full disk/memory, short oplog and bloat."""
    findings = _storage_capacity(sections)
    reclaimable, next_steps = _storage_reclaimable(sections)
    findings += reclaimable

    if not findings:
        findings.append("storage looks healthy: no near-full disk/memory, oplog or bloat signals")
    return findings, next_steps


def _summarize_tls(section: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn a TLS probe into findings about expiring certificates and unexpected plaintext."""
    findings: list[str] = []
    next_steps: list[str] = []

    if section.get("reachable") is False:
        findings.append(f"could not reach the server to inspect TLS ({section.get('note')})")
        return findings, next_steps
    if not section.get("tls"):
        if not tls_probe.is_local(section.get("host", "")):
            findings.append(f"the server offers no TLS ({section.get('note', 'plaintext')}) on a remote host")
            next_steps.append("enable TLS on the server or connect through a TLS-terminating proxy")
        else:
            findings.append("no TLS (local connection)")
        return findings, next_steps

    cert = section.get("certificate")
    if isinstance(cert, dict):
        days = cert.get("days_left")
        if isinstance(days, int) and days < 0:
            findings.append(f"the certificate expired {-days} days ago")
        elif isinstance(days, int) and days < 7:
            findings.append(f"the certificate expires in {days} days (renew now)")
        elif isinstance(days, int) and days < 30:
            findings.append(f"the certificate expires in {days} days")
        if cert.get("self_signed"):
            findings.append("the certificate is self-signed (clients must trust it explicitly)")
    if not findings:
        findings.append(f"TLS looks healthy: {section.get('protocol')} with a valid certificate")
    return findings, next_steps


def _config_pg(sections: dict[str, Any]) -> list[str]:
    """PostgreSQL cache/vacuum/checkpoint signals, plus the engine-agnostic connection-saturation check."""
    findings: list[str] = []
    cache = sections.get("cache")
    if isinstance(cache, dict):
        hit = _pct(cache.get("hits"), (cache.get("hits") or 0) + (cache.get("reads") or 0))
        if hit is not None and hit < 0.9:
            findings.append(f"buffer cache hit ratio is {round(hit * 100)}% (<90%): consider more shared_buffers")

    conns = sections.get("connections")
    if isinstance(conns, dict):
        used = _pct(conns.get("current"), conns.get("max"))
        if used is not None and used >= 0.8:
            findings.append(f"connections at {round(used * 100)}% of max: raise the cap or pool connections")

    behind = sections.get("autovacuum_behind_tables")
    if isinstance(behind, int) and behind > 0:
        findings.append(f"{behind} table(s) are past the autovacuum threshold: autovacuum may be too slow")

    checkpoints = sections.get("checkpoints")
    if isinstance(checkpoints, dict):
        req, timed = checkpoints.get("requested"), checkpoints.get("timed")
        if isinstance(req, int) and isinstance(timed, int) and req > timed:
            findings.append("more requested than timed checkpoints: raise max_wal_size to smooth I/O")
    return findings


def _config_mysql(sections: dict[str, Any]) -> list[str]:
    """MySQL/MariaDB buffer-pool sizing and temp-table-spill signals."""
    findings: list[str] = []
    data_bytes = sections.get("data_bytes")
    variables = sections.get("variables")
    if isinstance(data_bytes, int) and isinstance(variables, dict):
        pool = variables.get("innodb_buffer_pool_size")
        if pool is not None and int(pool) < data_bytes:
            findings.append("innodb_buffer_pool_size is smaller than the data: hot data may not stay cached")

    status = sections.get("status")
    if isinstance(status, dict):
        disk = _pct(status.get("Created_tmp_disk_tables"), status.get("Created_tmp_tables"))
        if disk is not None and disk >= 0.25:
            findings.append(f"{round(disk * 100)}% of temp tables spilled to disk: raise tmp_table_size")
    return findings


def _config_redis(sections: dict[str, Any]) -> list[str]:
    """Redis durability/eviction signals: unbounded memory, noeviction under pressure, no persistence."""
    findings: list[str] = []
    config = sections.get("config")
    if not isinstance(config, dict):
        return findings
    policy = config.get("maxmemory-policy")
    if config.get("maxmemory") == "0":
        findings.append("maxmemory is 0 (unbounded): Redis can consume all RAM and be OOM-killed")
    if policy == "noeviction" and isinstance(sections.get("evicted_keys"), int) and sections["evicted_keys"] == 0:
        findings.append("maxmemory-policy is noeviction: writes fail once maxmemory is hit")
    if config.get("appendonly") == "no" and not config.get("save"):
        findings.append("no persistence configured (appendonly off and empty save): data is memory-only")
    return findings


def _config_sqlite(sections: dict[str, Any]) -> list[str]:
    """SQLite journal-mode signal: non-WAL modes limit concurrency for most workloads."""
    journal = sections.get("journal_mode")
    if isinstance(journal, str) and journal.lower() != "wal":
        return [f"journal_mode is '{journal}': WAL improves concurrency for most workloads"]
    return []


def _summarize_config(engine: str, sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn raw config-vs-workload signals into heuristic findings, each naming its signal."""
    findings: list[str] = []
    for helper in (_config_pg, _config_mysql, _config_redis, _config_sqlite):
        findings += helper(sections)

    if not findings:
        findings.append("configuration looks reasonable for the observed signals")
    return findings, []


def _summarize_indexes(engine: str, sections: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Turn raw index-gap signals into findings, surfacing suggested indexes where available."""
    findings: list[str] = []
    next_steps: list[str] = []

    fks = sections.get("unindexed_foreign_keys")
    if isinstance(fks, list):
        for row in fks:
            findings.append(
                f"foreign key {row.get('constraint')} on {row.get('table')} ({row.get('columns')}) "
                f"has no covering index — suggested: {row.get('suggested')}"
            )
        if fks:
            next_steps.append("db_perf_explain with hypothetical_indexes to validate a suggestion before creating it")

    seq = sections.get("seq_scan_heavy")
    if isinstance(seq, list):
        for row in seq:
            findings.append(
                f"{row.get('table')} took {row.get('seq_scan')} sequential scans on {row.get('n_live_tup')} rows"
            )

    for key, label in (("full_scan_tables", "full-table scans"), ("collscans", "collection scans")):
        rows = sections.get(key)
        if isinstance(rows, list):
            for row in rows[:5]:
                name = row.get("object_name") or row.get("ns")
                findings.append(f"{name} shows repeated {label}")

    unindexed = sections.get("unindexed_tables")
    if isinstance(unindexed, list):
        for row in unindexed:
            findings.append(f"{row.get('table')} has {row.get('approx_rows')} rows and no secondary index")

    if not findings:
        findings.append("no obvious missing indexes from the current statistics")
    return findings, next_steps
