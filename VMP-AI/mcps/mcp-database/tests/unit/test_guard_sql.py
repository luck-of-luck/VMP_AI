import pytest

from mcp_database import guard
from mcp_database.config import parse_connection
from mcp_database.errors import AccessDeniedError, QueryValidationError
from mcp_database.guard import ToolClass


def make_cfg(**overrides):
    raw = {"uri": "postgresql://u@localhost/db", "access_mode": "read_write", **overrides}
    return parse_connection("test", raw)


HAPPY_READS = [
    "SELECT 1",
    "SELECT * FROM users WHERE id = 1",
    "select name, count(*) from orders group by 1 having count(*) > 2 order by 2 desc limit 5",
    "WITH recent AS (SELECT * FROM orders WHERE created_at > now() - interval '1 day') SELECT * FROM recent",
    "SELECT a FROM t1 UNION ALL SELECT b FROM t2",
    "-- leading comment\nSELECT 1",
    "SELECT 'emoji 😀 string'",
    "SELECT * FROM shop.orders o JOIN shop.customers c ON c.id = o.customer_id",
]


@pytest.mark.parametrize("query", HAPPY_READS)
@pytest.mark.parametrize("dialect", ["postgres", "mysql"])
def test_validate_read_happy(query, dialect):
    guard.validate_sql_read(query, dialect)


SAD_LOGICAL_READS = [
    "UPDATE users SET name = 'x'",
    "DELETE FROM users",
    "INSERT INTO users (name) VALUES ('x')",
    "CREATE TABLE t (id int)",
    "DROP TABLE users",
    "TRUNCATE users",
    "GRANT SELECT ON users TO bob",
    "ALTER TABLE users ADD COLUMN x int",
    "SELECT * INTO backup FROM users",
    "WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x",
    "SELECT pg_terminate_backend(123)",
    "SELECT pg_cancel_backend(123)",
    "SELECT pg_sleep(60)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT 1; SELECT 2",
]


@pytest.mark.parametrize("query", SAD_LOGICAL_READS)
def test_validate_read_sad_logical(query):
    with pytest.raises(QueryValidationError):
        guard.validate_sql_read(query, "postgres")


SAD_ABSURD_READS = [
    "",
    "   \n\t  ",
    "🤪🤪🤪",
    "SELECT * FROM users; DROP TABLE users; --",
    "not sql at all !!!",
    "))))((((",
    "x" * 100_000,
    None,
    42,
]


@pytest.mark.parametrize("query", SAD_ABSURD_READS)
def test_validate_read_sad_absurd(query):
    with pytest.raises(QueryValidationError):
        guard.validate_sql_read(query, "postgres")


class TestParseErrorMessage:
    @pytest.mark.parametrize("query", ["SELECT * FROM", "SELCT 1", "garbage (("])
    def test_message_is_clean_and_positional(self, query):
        with pytest.raises(QueryValidationError) as exc:
            guard.parse_sql(query, "postgres")
        message = str(exc.value)
        assert "Could not parse SQL" in message
        assert "fail-closed" in message
        # never leak sqlglot internals to the agent
        assert "Token" not in message
        assert "expressions." not in message
        assert "SENTINEL" not in message

    def test_mysql_percent_s_gets_a_cause_hint(self):
        with pytest.raises(QueryValidationError, match="modulo operator") as exc:
            guard.parse_sql("SELECT * FROM t WHERE a = %s", "mysql")
        assert "line 1" in str(exc.value)

    def test_postgres_percent_s_parses_without_hint(self):
        # psycopg %s placeholders are valid in the postgres dialect — no error, no hint.
        guard.validate_sql_read("SELECT * FROM t WHERE a = %s", "postgres")

    def test_fallback_message_when_no_structured_errors(self):
        # Tokenizer-level errors carry no `errors` list; the message stays clean and generic.
        from sqlglot.errors import SqlglotError

        from mcp_database.helpers import sql_ast

        assert sql_ast.describe_parse_error(SqlglotError("boom")) == "Could not parse SQL; rejecting (fail-closed)."


EXECUTABLE_COMMENT_SMUGGLED = [
    "/*!50000 DELETE FROM users */ SELECT 1",
    "/*! DROP TABLE users */ SELECT 1",
    "/*!99999 UPDATE users SET a = 1 */ SELECT 1",
    "SELECT 1 /*!50000, SLEEP(5) */",
    "SELECT/*!12345 1*/",
    "/*!\nDELETE FROM users\n*/ SELECT 1",
    "SELECT 1 /*!*/",
]


class TestExecutableCommentSmuggling:
    """MySQL executable comments (/*! ... */) run their contents but sqlglot sees inert comments.

    Confirmed against a real MySQL 8.4: `/*!50000 DELETE FROM t */` empties the table. The guard must
    reject the /*! marker fail-closed on every engine and every path (read and write), since a write can
    hide inside one and slip past the read allowlist and write_ops classification.
    """

    @pytest.mark.parametrize("query", EXECUTABLE_COMMENT_SMUGGLED)
    @pytest.mark.parametrize("dialect", ["mysql", "postgres"])
    def test_read_path_rejects_executable_comment(self, query, dialect):
        with pytest.raises(QueryValidationError, match="executable comment"):
            guard.validate_sql_read(query, dialect)

    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO t VALUES (1) /*!50000; DROP TABLE t */",
            "/*!50000 DROP TABLE t */ INSERT INTO t VALUES (1)",
            "UPDATE t SET a = 1 WHERE id = 1 /*! , b = 2 */",
        ],
    )
    def test_write_path_rejects_executable_comment(self, query):
        with pytest.raises(QueryValidationError, match="executable comment"):
            guard.analyze_sql_write(query, "mysql")

    @pytest.mark.parametrize(
        "query",
        ["SELECT 1 /* normal block */", "SELECT 1 -- trailing", "SELECT 1 # mysql hash", "SELECT 1 /*ok*/"],
    )
    def test_legitimate_comments_still_pass(self, query):
        """Only the /*! marker is barred; ordinary block/line/hash comments remain valid."""
        guard.validate_sql_read(query, "mysql")


def test_values_statement_per_dialect():
    guard.validate_sql_read("VALUES (1, 'x'), (2, 'y')", "postgres")
    guard.validate_sql_read("VALUES ROW(1, 'x'), ROW(2, 'y')", "mysql")


def test_mysql_sleep_forbidden():
    with pytest.raises(QueryValidationError, match="sleep"):
        guard.validate_sql_read("SELECT sleep(10)", "mysql")


@pytest.mark.parametrize("query", ["SELECT 1;", "SELECT 1;;", "SELECT 1 ;\n\t "])
def test_trailing_semicolons_still_count_as_one_statement(query):
    """Trailing semicolons produce empty parse slots, not extra statements, so the single-statement rule passes."""
    guard.validate_sql_read(query, "postgres")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("INSERT INTO t (a) VALUES (1)", "insert"),
        ("UPDATE t SET a = 1 WHERE id = 2", "update"),
        ("DELETE FROM t WHERE id = 1", "delete"),
        ("CREATE INDEX idx ON t (a)", "ddl"),
        ("DROP TABLE t", "ddl"),
        ("TRUNCATE t", "ddl"),
        ("ALTER TABLE t ADD COLUMN b int", "ddl"),
        ("GRANT SELECT ON t TO bob", "ddl"),
        ("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET a = s.a", "update"),
    ],
)
def test_classify_write_happy(query, expected):
    assert guard.classify_sql_write(query, "postgres") == expected


@pytest.mark.parametrize("query", ["SELECT 1", "VALUES (1)", "WITH x AS (SELECT 1) SELECT * FROM x"])
def test_classify_write_rejects_reads(query):
    with pytest.raises(QueryValidationError, match="db_read_query"):
        guard.classify_sql_write(query, "postgres")


@pytest.mark.parametrize("query", ["", "garbage ((", "INSERT INTO t VALUES (1); DROP TABLE t"])
def test_classify_write_rejects_absurd(query):
    with pytest.raises(QueryValidationError):
        guard.classify_sql_write(query, "postgres")


@pytest.mark.parametrize("query", ["1 + 1", ":param", "42"])
def test_classify_write_rejects_bare_expressions(query):
    with pytest.raises(QueryValidationError, match="Unsupported statement"):
        guard.classify_sql_write(query, "postgres")


def test_sql_databases_extraction():
    assert guard.sql_databases("SELECT * FROM shop.orders JOIN crm.leads ON true", "mysql") == {"shop", "crm"}
    assert guard.sql_databases("SELECT * FROM orders", "mysql") == set()


class TestApplyReadLimit:
    def test_injects_limit_when_absent(self):
        assert guard.apply_read_limit("SELECT * FROM t", "postgres", 501) == "SELECT * FROM t LIMIT 501"

    def test_injects_on_union(self):
        out = guard.apply_read_limit("SELECT a FROM t UNION SELECT a FROM u", "postgres", 10)
        assert out.endswith("LIMIT 10")

    def test_keeps_existing_limit_untouched(self):
        assert guard.apply_read_limit("SELECT * FROM t LIMIT 5", "postgres", 501) == "SELECT * FROM t LIMIT 5"

    def test_values_statement_is_untouched(self):
        assert guard.apply_read_limit("VALUES (1), (2)", "postgres", 501) == "VALUES (1), (2)"

    def test_preserves_order_by_before_limit(self):
        out = guard.apply_read_limit("SELECT * FROM t ORDER BY created_at DESC", "postgres", 100)
        assert "ORDER BY" in out and out.rstrip().endswith("LIMIT 100")


class TestSqlAuditShape:
    @pytest.mark.parametrize(
        ("query", "expected_absent"),
        [
            ("UPDATE users SET ssn = '123-45-6789' WHERE id = 42", ("123-45-6789", "42")),
            ("DELETE FROM users WHERE email = 'a@b.c'", ("a@b.c",)),
            ("INSERT INTO users (name) VALUES ('Alice')", ("Alice",)),
        ],
    )
    def test_literals_replaced_with_placeholders(self, query, expected_absent):
        shape = guard.analyze_sql_write(query, "postgres").audit_shape
        assert "?" in shape
        for secret in expected_absent:
            assert secret not in shape


class TestBoundedSqlWrite:
    @pytest.mark.parametrize(
        "query",
        ["DELETE FROM users", "UPDATE users SET plan = 'pro'", "update orders set status = 'done', total = 0"],
    )
    def test_rejects_missing_where(self, query):
        info = guard.analyze_sql_write(query, "postgres")
        assert info.unbounded is True
        with pytest.raises(QueryValidationError, match="no WHERE clause"):
            guard.ensure_bounded_sql_write(info.op, info.unbounded)

    @pytest.mark.parametrize(
        "query",
        [
            "DELETE FROM users WHERE id = 1",
            "UPDATE users SET plan = 'pro' WHERE id = 1",
            "DELETE FROM users WHERE 1 = 1",  # still bounded by a (useless) predicate — model's call
        ],
    )
    def test_allows_write_with_where(self, query):
        info = guard.analyze_sql_write(query, "postgres")
        assert info.unbounded is False
        guard.ensure_bounded_sql_write(info.op, info.unbounded)

    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO users (id) VALUES (1)",  # insert adds explicit rows, not a mass mutation
            "TRUNCATE TABLE users",  # DDL, deliberately left allowed
            "DROP TABLE users",
        ],
    )
    def test_ignores_non_mutations(self, query):
        info = guard.analyze_sql_write(query, "postgres")
        assert info.unbounded is False
        guard.ensure_bounded_sql_write(info.op, info.unbounded)


MATRIX = [
    ("read_write", ToolClass.SCHEMA, True),
    ("read_write", ToolClass.READ, True),
    ("read_write", ToolClass.PERF, True),
    ("read_write", ToolClass.WRITE, True),
    ("read_write", ToolClass.ADMIN, True),
    ("read_only", ToolClass.SCHEMA, True),
    ("read_only", ToolClass.READ, True),
    ("read_only", ToolClass.PERF, True),
    ("read_only", ToolClass.WRITE, False),
    ("read_only", ToolClass.ADMIN, False),
    ("monitor", ToolClass.SCHEMA, True),
    ("monitor", ToolClass.READ, False),
    ("monitor", ToolClass.PERF, True),
    ("monitor", ToolClass.WRITE, False),
    ("monitor", ToolClass.ADMIN, False),
]


@pytest.mark.parametrize(("mode", "tool_class", "allowed"), MATRIX)
def test_mode_matrix(mode, tool_class, allowed):
    cfg = make_cfg(access_mode=mode)
    if allowed:
        guard.ensure_tool_allowed(cfg, tool_class)
    else:
        with pytest.raises(AccessDeniedError):
            guard.ensure_tool_allowed(cfg, tool_class)


def test_database_modes_override():
    cfg = make_cfg(access_mode="read_write", database_modes={"prod": "read_only"})
    guard.ensure_tool_allowed(cfg, ToolClass.WRITE, "dev")
    with pytest.raises(AccessDeniedError, match="prod"):
        guard.ensure_tool_allowed(cfg, ToolClass.WRITE, "prod")


def test_denial_scope_suffix_only_for_listed_databases():
    """The denial names the database only when its mode came from database_modes, not from the connection default."""
    cfg = make_cfg(access_mode="monitor", database_modes={"prod": "read_only"})
    with pytest.raises(AccessDeniedError, match="for database 'prod'"):
        guard.ensure_tool_allowed(cfg, ToolClass.WRITE, "prod")
    with pytest.raises(AccessDeniedError) as excinfo:
        guard.ensure_tool_allowed(cfg, ToolClass.READ, "other")
    assert "for database" not in str(excinfo.value)


def test_unqualified_query_uses_most_restrictive_mode():
    cfg = make_cfg(access_mode="read_write", database_modes={"prod": "monitor"})
    with pytest.raises(AccessDeniedError):
        guard.ensure_databases_allowed(cfg, ToolClass.READ, set())


def test_ensure_databases_checks_each_qualifier():
    cfg = make_cfg(access_mode="read_write", database_modes={"prod": "read_only"})
    guard.ensure_databases_allowed(cfg, ToolClass.WRITE, {"dev"})
    with pytest.raises(AccessDeniedError):
        guard.ensure_databases_allowed(cfg, ToolClass.WRITE, {"dev", "prod"})


def test_write_ops_restriction():
    cfg = make_cfg(write_ops=["insert", "update"])
    guard.ensure_write_op_allowed(cfg, "insert")
    with pytest.raises(AccessDeniedError, match="delete"):
        guard.ensure_write_op_allowed(cfg, "delete")
    with pytest.raises(AccessDeniedError, match="ddl"):
        guard.ensure_write_op_allowed(cfg, "ddl")
