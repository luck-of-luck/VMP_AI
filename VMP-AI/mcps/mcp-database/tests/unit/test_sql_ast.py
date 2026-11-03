import pytest
import sqlglot
from sqlglot.errors import SqlglotError

from mcp_database.errors import QueryValidationError
from mcp_database.guard import parse_sql
from mcp_database.helpers import sql_ast


def tree(query, dialect="postgres"):
    return parse_sql(query, dialect)


def test_describe_parse_error_includes_position():
    try:
        sqlglot.parse("SELECT * FROM WHERE x =", read="postgres")
    except SqlglotError as exc:
        message = sql_ast.describe_parse_error(exc)
    assert "fail-closed" in message
    assert "line" in message


def test_describe_parse_error_without_details_is_generic():
    assert "fail-closed" in sql_ast.describe_parse_error(SqlglotError("boom"))


@pytest.mark.parametrize(
    "query",
    ["SELECT 1", "SELECT a FROM t UNION SELECT b FROM u", "VALUES (1), (2)"],
)
def test_ensure_read_root_happy(query):
    sql_ast.ensure_read_root(tree(query))


@pytest.mark.parametrize(
    "query",
    ["INSERT INTO t VALUES (1)", "UPDATE t SET a = 1", "DROP TABLE t", "SELECT * INTO backup FROM t"],
)
def test_ensure_read_root_sad(query):
    with pytest.raises(QueryValidationError):
        sql_ast.ensure_read_root(tree(query))


def test_ensure_no_embedded_writes_happy_with_subquery():
    sql_ast.ensure_no_embedded_writes(tree("SELECT * FROM (SELECT 1 AS x) s WHERE x IN (SELECT 1)"))


def test_ensure_no_embedded_writes_sad_cte_delete():
    with pytest.raises(QueryValidationError):
        sql_ast.ensure_no_embedded_writes(tree("WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x"))


@pytest.mark.parametrize(
    "query",
    [
        "SELECT PG_SLEEP(1)",
        "SELECT * FROM t WHERE x = pg_read_file('/etc/passwd')",
        "SELECT dblink('conn', 'SELECT 1')",
    ],
)
def test_forbidden_functions_sad_any_casing_or_position(query):
    with pytest.raises(QueryValidationError):
        sql_ast.ensure_no_forbidden_functions(tree(query))


@pytest.mark.parametrize("query", ["SELECT count(*) FROM t", "SELECT my_custom_fn(1)", "SELECT now()"])
def test_forbidden_functions_happy(query):
    sql_ast.ensure_no_forbidden_functions(tree(query))


@pytest.mark.parametrize(
    ("query", "op"),
    [
        ("INSERT INTO t VALUES (1)", "insert"),
        ("UPDATE t SET a = 1 WHERE id = 1", "update"),
        ("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET x = 1", "update"),
        ("DELETE FROM t WHERE id = 1", "delete"),
        ("CREATE TABLE t (id int)", "ddl"),
        ("DROP TABLE t", "ddl"),
        ("TRUNCATE TABLE t", "ddl"),
        ("GRANT SELECT ON t TO bob", "ddl"),
        ("SET foo = 1", "ddl"),
    ],
)
def test_classify_write_tree(query, op):
    assert sql_ast.classify_write_tree(tree(query)) == op


def test_classify_write_tree_rejects_reads():
    with pytest.raises(QueryValidationError, match="read statement"):
        sql_ast.classify_write_tree(tree("SELECT 1"))


@pytest.mark.parametrize(
    ("query", "unbounded"),
    [
        ("UPDATE t SET a = 1", True),
        ("DELETE FROM t", True),
        ("UPDATE t SET a = 1 WHERE id = 1", False),
        ("DELETE FROM t WHERE id = 1", False),
        ("INSERT INTO t VALUES (1)", False),
    ],
)
def test_is_unbounded_mutation(query, unbounded):
    assert sql_ast.is_unbounded_mutation(tree(query)) is unbounded


def test_with_row_limit_injects_when_missing():
    limited, injected = sql_ast.with_row_limit(tree("SELECT * FROM t"), 5)
    assert injected
    assert "LIMIT 5" in limited.sql(dialect="postgres")


def test_with_row_limit_keeps_existing_limit():
    limited, injected = sql_ast.with_row_limit(tree("SELECT * FROM t LIMIT 3"), 5)
    assert not injected
    assert "LIMIT 3" in limited.sql(dialect="postgres")


def test_with_row_limit_leaves_values_untouched():
    _, injected = sql_ast.with_row_limit(tree("VALUES (1), (2)"), 5)
    assert not injected


def test_normalize_literals_strips_values():
    shape = sql_ast.normalize_literals(tree("SELECT * FROM users WHERE email = 'a@b' AND id = 42"))
    assert "a@b" not in shape
    assert "42" not in shape
    assert shape.count("?") == 2


def test_normalize_literals_strips_unicode_values():
    shape = sql_ast.normalize_literals(tree("UPDATE t SET name = 'José 😀' WHERE id = 1"))
    assert "José" not in shape


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("SELECT * FROM users", set()),
        ("SELECT * FROM shop.orders", {"shop"}),
        ("SELECT * FROM cat.sch.t JOIN shop.orders o ON 1 = 1", {"cat", "sch", "shop"}),
    ],
)
def test_database_qualifiers(query, expected):
    assert sql_ast.database_qualifiers(tree(query)) == expected


class TestCountProbe:
    """count_probe rewrites a simple UPDATE/DELETE as SELECT count(*), or refuses when it can't be exact."""

    def test_update_with_where(self):
        probe = sql_ast.count_probe(tree("UPDATE t SET a = 1 WHERE id = 2"))
        assert probe.sql() == "SELECT COUNT(*) AS n FROM t WHERE id = 2"

    def test_delete_without_where(self):
        probe = sql_ast.count_probe(tree("DELETE FROM t"))
        assert probe.sql() == "SELECT COUNT(*) AS n FROM t"

    def test_qualified_table_and_unicode_literal(self):
        probe = sql_ast.count_probe(tree("DELETE FROM shop.orders WHERE note = 'café 🚀'"))
        assert probe.sql() == "SELECT COUNT(*) AS n FROM shop.orders WHERE note = 'café 🚀'"

    @pytest.mark.parametrize(
        ("query", "dialect"),
        [
            ("UPDATE t SET a = 1 FROM u WHERE t.id = u.id", "postgres"),
            ("DELETE FROM t USING u WHERE t.id = u.id", "postgres"),
            ("DELETE FROM t WHERE id = 1 RETURNING id", "postgres"),
            ("DELETE FROM t ORDER BY id LIMIT 5", "mysql"),
            ("WITH doomed AS (SELECT id FROM t) DELETE FROM t WHERE id IN (SELECT id FROM doomed)", "postgres"),
        ],
    )
    def test_refuses_anything_beyond_single_table(self, query, dialect):
        assert sql_ast.count_probe(tree(query, dialect)) is None

    @pytest.mark.parametrize("query", ["INSERT INTO t (a) VALUES (1)", "SELECT 1", "DROP TABLE t"])
    def test_refuses_non_mutations(self, query):
        assert sql_ast.count_probe(sqlglot.parse_one(query, read="postgres")) is None


def test_count_probe_without_a_table_target_returns_none():
    """A mutation whose target is not a plain table is not probeable."""
    from sqlglot import exp

    assert sql_ast.count_probe(exp.Delete()) is None
