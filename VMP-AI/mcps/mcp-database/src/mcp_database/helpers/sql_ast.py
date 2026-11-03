from __future__ import annotations

from sqlglot import exp
from sqlglot.errors import SqlglotError

from ..errors import QueryValidationError


def resolve_exp_types(*names: str) -> tuple[type[exp.Expression], ...]:
    """Resolve sqlglot node classes by name, skipping names this sqlglot version does not define."""
    return tuple(t for t in (getattr(exp, n, None) for n in names) if isinstance(t, type))


def describe_parse_error(exc: SqlglotError) -> str:
    """Turn a sqlglot parse error into a short, agent-actionable message (position, not internal repr)."""
    errors = getattr(exc, "errors", None)
    if errors:
        first = errors[0]
        highlight, line, col = first.get("highlight"), first.get("line"), first.get("col")
        where = f" near {highlight!r}" if highlight else ""
        position = f" (line {line}, col {col})" if line and col else ""
        return f"Could not parse SQL{where}{position}; rejecting (fail-closed)."
    return "Could not parse SQL; rejecting (fail-closed)."


READ_ROOTS = resolve_exp_types("Select", "SetOperation", "Union", "Intersect", "Except", "Values")
WRITE_NODES = resolve_exp_types("Insert", "Update", "Delete", "Merge")
DDL_NODES = resolve_exp_types(
    "Create", "Drop", "Alter", "AlterTable", "TruncateTable", "Truncate", "Grant", "Revoke", "Comment", "Rename"
)
COMMAND_NODES = resolve_exp_types(
    "Command",
    "Set",
    "Use",
    "Transaction",
    "Commit",
    "Rollback",
    "Call",
    "Pragma",
    "Copy",
    "LoadData",
    "Show",
    "Describe",
    "Kill",
    "Analyze",
    "Vacuum",
)
NON_READ_NODES = WRITE_NODES + DDL_NODES + COMMAND_NODES

FORBIDDEN_FUNCTIONS = frozenset(
    {
        "pg_terminate_backend",
        "pg_cancel_backend",
        "pg_reload_conf",
        "pg_rotate_logfile",
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "lo_import",
        "lo_export",
        "dblink",
        "dblink_exec",
        "pg_sleep",
        "load_file",
        "sleep",
        "benchmark",
    }
)

WRITE_KINDS: tuple[tuple[tuple[type[exp.Expression], ...], str], ...] = (
    ((exp.Insert,), "insert"),
    ((exp.Update, exp.Merge), "update"),
    ((exp.Delete,), "delete"),
    (DDL_NODES + COMMAND_NODES, "ddl"),
)


def ensure_read_root(tree: exp.Expression) -> None:
    """The statement root must be a read (SELECT/UNION/VALUES); SELECT INTO is rejected too."""
    if not isinstance(tree, READ_ROOTS):
        raise QueryValidationError(
            f"Only read statements (SELECT/UNION/VALUES) are allowed here, got {type(tree).__name__.upper()}. "
            "Use db_write_query for writes."
        )
    if tree.args.get("into"):
        raise QueryValidationError("SELECT INTO creates a table and is not allowed in read tools")


def ensure_no_embedded_writes(tree: exp.Expression) -> None:
    """Reject reads that hide a write anywhere in the tree (CTE DML, subquery DML, commands)."""
    for node in tree.walk():
        if isinstance(node, NON_READ_NODES):
            raise QueryValidationError(f"Statement embeds a non-read operation: {type(node).__name__.upper()}")


def ensure_no_forbidden_functions(tree: exp.Expression) -> None:
    """Reject calls to admin/sleep/file functions (pg_sleep, benchmark, load_file, ...) in reads."""
    for node in tree.walk():
        if isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in FORBIDDEN_FUNCTIONS:
                raise QueryValidationError(f"Function '{name}' is not allowed in read tools")


def classify_write_tree(tree: exp.Expression) -> str:
    """Map a write statement to its kind: insert, update (incl. MERGE), delete or ddl."""
    for node_types, op in WRITE_KINDS:
        if isinstance(tree, node_types):
            return op
    if isinstance(tree, READ_ROOTS):
        raise QueryValidationError("This is a read statement; use db_read_query instead")
    raise QueryValidationError(f"Unsupported statement for db_write_query: {type(tree).__name__.upper()}")


def is_unbounded_mutation(tree: exp.Expression) -> bool:
    """True for an UPDATE/DELETE with no WHERE clause (would touch every row)."""
    return isinstance(tree, exp.Update | exp.Delete) and tree.args.get("where") is None


def with_row_limit(tree: exp.Expression, limit: int) -> tuple[exp.Expression, bool]:
    """Add a LIMIT to a SELECT/UNION that lacks one, so the database bounds the work at the source.

    Returns (tree, injected). Statements that already carry a LIMIT, and non-query roots like VALUES,
    are returned untouched.
    """
    if not isinstance(tree, exp.Query) or tree.args.get("limit") is not None:
        return tree, False
    return tree.limit(limit), True


def count_probe(tree: exp.Expression) -> exp.Select | None:
    """A SELECT count(*) equivalent of a simple UPDATE/DELETE, estimating affected rows without running it.

    Returns None for anything beyond one plain target table plus optional WHERE (joins, USING, ORDER BY,
    LIMIT, RETURNING, CTEs): there, only real execution knows the row count.
    """
    if not isinstance(tree, exp.Update | exp.Delete):
        return None
    allowed = {"this", "where", "expressions"} if isinstance(tree, exp.Update) else {"this", "where"}
    if any(key not in allowed and value for key, value in tree.args.items()):
        return None
    target = tree.this
    if not isinstance(target, exp.Table):
        return None
    probe = exp.select("COUNT(*) AS n").from_(target.copy())
    if where := tree.args.get("where"):
        probe.set("where", where.copy())
    return probe


def normalize_literals(tree: exp.Expression) -> str:
    """Render the statement with every literal replaced by a `?` placeholder (privacy-preserving shape)."""
    shape = tree.transform(lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node)
    return shape.sql()


def database_qualifiers(tree: exp.Expression) -> set[str]:
    """Every catalog/database qualifier referenced by the statement's tables."""
    qualifiers: set[str] = set()
    for table in tree.find_all(exp.Table):
        for part in ("catalog", "db"):
            if name := table.text(part):
                qualifiers.add(name)
    return qualifiers
