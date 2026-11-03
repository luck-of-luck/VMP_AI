from __future__ import annotations

from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

SAFE = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
MAINTENANCE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)

Conn = Annotated[str, Field(description="Name of a configured connection; discover them with db_schema_connections")]
Query = Annotated[
    str | dict[str, Any],
    Field(
        description=(
            "SQL string for postgres/mysql (SELECT/UNION/VALUES only, single statement). For mongodb, a JSON "
            'object: {"collection": str, "operation": "find|aggregate|countDocuments|estimatedDocumentCount'
            '|distinct|listIndexes", plus operation fields such as "filter", "pipeline", "sort", "key", '
            'and optional "database"}'
        )
    ),
]
WriteQuery = Annotated[
    str | dict[str, Any],
    Field(
        description=(
            "DML/DDL SQL string for postgres/mysql (single statement). For mongodb, a JSON object: "
            '{"collection": str, "operation": "insertOne|insertMany|updateOne|updateMany|replaceOne|deleteOne'
            '|deleteMany|createIndex|dropIndex|createCollection|dropCollection|renameCollection", plus fields '
            'such as "documents", "filter", "update", "keys", "options", "to", and optional "database"}'
        )
    ),
]
Database = Annotated[str, Field(description="Database name (MySQL/MongoDB) or schema name (PostgreSQL)")]
DatabaseFilter = Annotated[
    str | None, Field(description="Optional database (MySQL/MongoDB) or schema (PostgreSQL) to filter by")
]
ObjectName = Annotated[str, Field(description="Table, view or collection name")]
ObjectFilter = Annotated[str | None, Field(description="Optional table, view or collection name to filter by")]
RowLimit = Annotated[
    int | None,
    Field(description="Maximum rows/documents to return (default: the connection's row_limit; hard cap 5000)"),
]
DryRun = Annotated[
    bool, Field(description="Execute inside a transaction and roll back, reporting how many rows would be affected")
]
ExpectedMaxRows = Annotated[
    int | None,
    Field(description="Abort with rollback if the write would affect more rows than this (catches missing WHERE)"),
]
SearchPattern = Annotated[str, Field(description="Substring to match against object/column names (case-insensitive)")]
ColumnFilter = Annotated[str | None, Field(description="Optional column name to filter by; omit for every column")]
SortBy = Annotated[str, Field(description="Sort column: total_time | mean_time | calls | rows")]
TargetId = Annotated[str, Field(description="Backend pid (PostgreSQL), thread id (MySQL) or opid (MongoDB)")]
AnalyzeFlag = Annotated[
    bool, Field(description="Run the query for real timings (EXPLAIN ANALYZE); only accepted for read queries")
]
HypotheticalIndexes = Annotated[
    list[str] | None,
    Field(
        description=(
            "CREATE INDEX statements to simulate before planning (PostgreSQL with the hypopg extension); "
            "the indexes are never actually created and cannot be combined with analyze=true"
        )
    ),
]
ExportPath = Annotated[str, Field(description="Local file path to write the result to (parent dirs are created)")]
ExportFormat = Annotated[str, Field(description="Output format: json | csv")]
SampleN = Annotated[int, Field(description="Number of sample rows/documents to fetch (hard cap 5000)")]
Vector = Annotated[
    list[float],
    Field(description="Pre-computed query embedding as a JSON array of numbers; length must match the index"),
]
VectorColumn = Annotated[str, Field(description="Column (SQL) or field path (MongoDB) holding the vectors")]
VectorMetric = Annotated[
    str,
    Field(
        description=(
            "Distance metric on PostgreSQL: cosine | l2 | inner_product | l1. "
            "MongoDB uses the similarity baked into the index and ignores this"
        )
    ),
]
SearchIndexName = Annotated[
    str | None,
    Field(
        description=(
            "Atlas Search index name: required for MongoDB vector search, defaults to 'default' for text "
            "search; rejected on SQL engines"
        )
    ),
]
SearchFilter = Annotated[
    dict[str, Any] | None,
    Field(
        description=(
            "Optional pre-filter: flat column->value equality object on SQL engines; "
            "a MongoDB filter expression on mongodb"
        )
    ),
]
NumCandidates = Annotated[
    int | None,
    Field(
        description=(
            "MongoDB $vectorSearch numCandidates (default 10x the row limit, bounded to [100, 10000]); "
            "rejected on SQL engines"
        )
    ),
]
TextQuery = Annotated[
    str, Field(description="Free-text search phrase (treated as literal text, never a regex or pattern language)")
]
SearchColumn = Annotated[
    str | None,
    Field(
        description=(
            "Column (SQL) or field path (MongoDB) holding the text; required on SQL engines, "
            "omit on MongoDB to search every indexed field"
        )
    ),
]
TsLanguage = Annotated[
    str | None,
    Field(
        description=(
            "PostgreSQL text-search configuration (regconfig such as 'english'; default 'simple'); "
            "rejected on other engines"
        )
    ),
]
IndexAction = Annotated[
    str, Field(description="create | update | drop (update is Atlas-only; SQL engines guide to drop+create)")
]
IndexName = Annotated[str, Field(description="Name of the search/vector index")]
IndexDefinition = Annotated[
    dict[str, Any] | None,
    Field(
        description=(
            'Index definition for create/update. PostgreSQL: {"column": str, "method": "hnsw|ivfflat", '
            '"metric": "cosine|l2|inner_product|l1", "options": {"m"|"ef_construction"|"lists": int}}. '
            'MySQL: {"columns": [str, ...]} (FULLTEXT). MongoDB Atlas: {"fields": [...]} for vectorSearch '
            'or {"mappings": {...}} for text search (optional "type" to override)'
        )
    ),
]
ClusterAction = Annotated[
    str,
    Field(
        description=(
            "promote / pause_replay / resume_replay (PostgreSQL replica) | start_replica / stop_replica "
            "(MySQL replica) | step_down / freeze (MongoDB replica set) | promote (Redis replica)"
        )
    ),
]
ClusterSeconds = Annotated[
    int | None,
    Field(
        description=(
            "Duration in seconds: PostgreSQL promote wait, MongoDB step_down (default 60) and freeze "
            "(required; 0 unfreezes); rejected for MySQL actions"
        )
    ),
]
